import pandas as pd
import numpy as np
import ast
import os
import gc
import json
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from pathlib import Path

import torch
from tqdm.auto import tqdm

from llama_index.core import VectorStoreIndex, Document, Settings, StorageContext
from llama_index.vector_stores.qdrant import QdrantVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.huggingface import HuggingFaceLLM
from llama_index.core.node_parser import SentenceSplitter, HierarchicalNodeParser
from llama_index.core.retrievers import QueryFusionRetriever, BaseRetriever
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.retrievers.bm25 import BM25Retriever
from qdrant_client import QdrantClient
from transformers import BitsAndBytesConfig
from sentence_transformers import CrossEncoder


QDRANT_HOST = os.getenv('QDRANT_HOST', 'localhost')
QDRANT_PORT = int(os.getenv('QDRANT_PORT', 6333))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = DATA_DIR / "logs"
MODELS_CACHE = DATA_DIR / "models_cache"

for dir_path in [DATA_DIR, LOGS_DIR, MODELS_CACHE]:
    dir_path.mkdir(parents=True, exist_ok=True)

QDRANT_BASE_PATH = str(DATA_DIR)
ARTIFACTS_DIR = str(DATA_DIR)


@dataclass
class ChunkingConfig:
    chunk_size: int = 512
    chunk_overlap: int = 100
    use_hierarchical: bool = False
    child_chunk_size: int = 128

@dataclass
class RetrievalConfig:
    top_k: int = 5
    overfetch_k: int = 15
    mode: str = "dense"
    use_reranker: bool = False
    rerank_top_n: int = 5

@dataclass
class LLMConfig:
    model_name: str = "Qwen/Qwen3-4B-Instruct-2507"
    max_new_tokens: int = 256
    context_window: int = 2048
    load_in_4bit: bool = True
    e2e_eval_n: int = 10
    prompt_template: str = "Context:\n{context_str}\n\nQuery: {query_str}\nAnswer:"

@dataclass
class EmbeddingConfig:
    model_name: str = "BAAI/bge-m3"
    truncate_dim: Optional[int] = None

@dataclass
class RAGConfig:
    name: str = "baseline"
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    qdrant_collection: str = "dense_base"
    recreate_collection: bool = False
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"


cfg_matryoshka = RAGConfig(
    name="matryoshka_512",
    embedding=EmbeddingConfig(truncate_dim=512),
    chunking=ChunkingConfig(chunk_size=512, chunk_overlap=100),
    retrieval=RetrievalConfig(top_k=5, overfetch_k=15, mode="dense", use_reranker=False),
    qdrant_collection="matryoshka_512",
    recreate_collection=False
)

cfg_hybrid_rerank = RAGConfig(
    name="advanced_full",
    chunking=ChunkingConfig(chunk_size=768, chunk_overlap=150),
    retrieval=RetrievalConfig(top_k=5, overfetch_k=25, mode="hybrid", use_reranker=True, rerank_top_n=5),
    qdrant_collection="advanced",
    recreate_collection=False
)

cfg_hybrid_only = RAGConfig(
    name="hybrid_only",
    chunking=ChunkingConfig(chunk_size=768, chunk_overlap=150),
    retrieval=RetrievalConfig(top_k=5, overfetch_k=15, mode="hybrid", use_reranker=False),
    qdrant_collection="hybrid_only",
    recreate_collection=False
)

cfg_rerank_only = RAGConfig(
    name="rerank_only",
    chunking=ChunkingConfig(chunk_size=768, chunk_overlap=150),
    retrieval=RetrievalConfig(top_k=5, overfetch_k=25, mode="dense", use_reranker=True, rerank_top_n=5),
    qdrant_collection="rerank_only",
    recreate_collection=False
)


_CACHED_LLM = None
_CACHED_EMBED = None
_CACHED_RERANKER = None


def _parse_list_field(value):
    if value is None:
        return []
    if isinstance(value, np.ndarray):
        return value.tolist()
    try:
        if pd.isna(value):
            return []
    except (ValueError, TypeError):
        pass
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value or value == '[]':
            return []
        try:
            if value.startswith('['):
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else [parsed]
        except:
            pass
        return [v.strip() for v in value.split(',') if v.strip()]
    return [value] if value else []


def unload_embedder():
    global _CACHED_EMBED
    if _CACHED_EMBED:
        del _CACHED_EMBED
        _CACHED_EMBED = None
        Settings.embed_model = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    logger.info("Эмбеддер выгружен")


def unload_llm():
    global _CACHED_LLM
    if _CACHED_LLM:
        del _CACHED_LLM
        _CACHED_LLM = None
        Settings.llm = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    logger.info("LLM выгружена")


def unload_reranker():
    global _CACHED_RERANKER
    if _CACHED_RERANKER:
        del _CACHED_RERANKER
        _CACHED_RERANKER = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    logger.info("Реранкер выгружен")


def get_embedder(cfg: EmbeddingConfig):
    global _CACHED_EMBED
    if _CACHED_EMBED:
        return _CACHED_EMBED
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Загрузка эмбеддера {cfg.model_name} на {device}")
    
    try:
        _CACHED_EMBED = HuggingFaceEmbedding(
            model_name=cfg.model_name,
            device=device,
            normalize=True,
            truncate_dim=cfg.truncate_dim,
            cache_folder=str(MODELS_CACHE)
        )
        logger.info("Эмбеддер успешно загружен")
        return _CACHED_EMBED
    except Exception as e:
        logger.error(f"Ошибка загрузки эмбеддера {cfg.model_name}: {e}")
        logger.info("Пробуем загрузить fallback модель BAAI/bge-small-en-v1.5")
        _CACHED_EMBED = HuggingFaceEmbedding(
            model_name="BAAI/bge-small-en-v1.5",
            device=device,
            normalize=True,
            cache_folder=str(MODELS_CACHE)
        )
        return _CACHED_EMBED


def get_llm(cfg: LLMConfig):
    global _CACHED_LLM
    if _CACHED_LLM:
        return _CACHED_LLM
    
    logger.info(f"Загрузка LLM {cfg.model_name}")
    try:
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4"
        )
        _CACHED_LLM = HuggingFaceLLM(
            model_name=cfg.model_name,
            context_window=cfg.context_window,
            max_new_tokens=cfg.max_new_tokens,
            model_kwargs={"quantization_config": bnb} if cfg.load_in_4bit else {},
            generate_kwargs={"do_sample": False},
            device_map="auto"
        )
        logger.info("LLM успешно загружена")
        return _CACHED_LLM
    except Exception as e:
        logger.error(f"Ошибка загрузки LLM: {e}")
        return None


def get_reranker(model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
    global _CACHED_RERANKER
    if _CACHED_RERANKER:
        return _CACHED_RERANKER
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Загрузка реранкера {model_name} на {device}")
    
    try:
        _CACHED_RERANKER = CrossEncoder(
            model_name,
            device=device,
            cache_dir=str(MODELS_CACHE)
        )
        logger.info("Реранкер успешно загружен")
        return _CACHED_RERANKER
    except Exception as e:
        logger.error(f"Ошибка загрузки реранкера: {e}")
        return None


def rerank_results(query: str, results: List[Dict], reranker, top_k: int = 5) -> List[Dict]:
    if not results or reranker is None:
        return results[:top_k]
    
    try:
        pairs = [(query, res['text']) for res in results]
        scores = reranker.predict(pairs)
        for i, score in enumerate(scores):
            results[i]['rerank_score'] = float(score)
        reranked = sorted(results, key=lambda x: x.get('rerank_score', 0), reverse=True)
        logger.info(f"Реранжирование завершено. Топ скор: {reranked[0].get('rerank_score', 0):.4f}")
        return reranked[:top_k]
    except Exception as e:
        logger.error(f"Ошибка при реранжировании: {e}")
        return results[:top_k]


class FilteredRetriever(BaseRetriever):
    def __init__(self, base_retriever: BaseRetriever, df_corpus: pd.DataFrame):
        super().__init__()
        self.base_retriever = base_retriever
        self.df_corpus = df_corpus

        if 'doc_id' not in self.df_corpus.columns:
            self.df_corpus = self.df_corpus.copy()
            self.df_corpus['doc_id'] = self.df_corpus.index

        self.doc_metadata = {}
        for idx, row in self.df_corpus.iterrows():
            doc_id = row['doc_id']
            try:
                hubs = _parse_list_field(row.get('hubs', []))
                tags = _parse_list_field(row.get('tags', []))
                url = row.get('url', '')
            except Exception as e:
                logger.warning(f"Ошибка обработки документа {doc_id}: {e}")
                hubs = []
                tags = []
                url = ''

            self.doc_metadata[doc_id] = {
                'hubs': hubs,
                'tags': tags,
                'url': url
            }

    def _retrieve(self, query_bundle: QueryBundle) -> List[NodeWithScore]:
        nodes = self.base_retriever.retrieve(query_bundle)
        filters = getattr(query_bundle, 'filters', None)

        if filters is None:
            return nodes

        filtered_nodes = []
        for node in nodes:
            doc_id = node.metadata.get('doc_id')
            if doc_id is None:
                continue

            doc_info = self.doc_metadata.get(doc_id)
            if doc_info is None:
                continue

            hubs = doc_info.get('hubs', [])
            tags = doc_info.get('tags', [])

            include = True

            if 'hubs' in filters and filters['hubs']:
                if not any(hub in hubs for hub in filters['hubs']):
                    include = False

            if 'tags' in filters and filters['tags'] and include:
                if not any(tag in tags for tag in filters['tags']):
                    include = False

            if include:
                node.metadata['url'] = doc_info.get('url', '')
                node.metadata['hubs'] = hubs
                node.metadata['tags'] = tags
                filtered_nodes.append(node)

        return filtered_nodes


class SearchEngine:
    def __init__(self, df_corpus: pd.DataFrame, config: RAGConfig = None):
        self.df_corpus = df_corpus
        self.config = config or RAGConfig()
        self.query_engine = None
        self.index = None
        self.retriever = None
        self.filtered_retriever = None
        self.reranker = None

    def build(self, load_llm: bool = False):
        logger.info(f"Построение индекса для {self.config.name}...")

        Settings.embed_model = get_embedder(self.config.embedding)

        if load_llm:
            try:
                Settings.llm = get_llm(self.config.llm)
            except Exception as e:
                logger.warning(f"Предупреждение: Не удалось загрузить LLM: {e}")
                Settings.llm = None
        else:
            Settings.llm = None

        if self.config.retrieval.use_reranker:
            self.reranker = get_reranker(self.config.rerank_model)

        logger.info(f"Подключение к Qdrant серверу: {QDRANT_HOST}:{QDRANT_PORT}")
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        vector_store = QdrantVectorStore(
            client=client,
            collection_name=self.config.qdrant_collection
        )

        collections = client.get_collections().collections
        collection_exists = any(col.name == self.config.qdrant_collection for col in collections)

        all_nodes = []

        if not collection_exists or self.config.recreate_collection:
            logger.info(f"Создание новой коллекции: {self.config.qdrant_collection}")
            documents = []

            for idx, row in tqdm(self.df_corpus.iterrows(), total=len(self.df_corpus), desc="Создание документов"):
                text = row.get("text", "")
                if not text or pd.isna(text):
                    continue

                doc = Document(
                    text=str(text),
                    metadata={
                        "doc_id": row.get("doc_id", idx),
                        "title": row.get("title", ""),
                        "url": row.get("url", "")
                    }
                )
                documents.append(doc)

            if not documents:
                raise ValueError("Нет документов для индексации")

            if self.config.chunking.use_hierarchical:
                node_parser = HierarchicalNodeParser.from_defaults(
                    chunk_sizes=[
                        self.config.chunking.chunk_size,
                        self.config.chunking.child_chunk_size
                    ]
                )
                all_nodes = node_parser.get_nodes_from_documents(documents)
            else:
                splitter = SentenceSplitter(
                    chunk_size=self.config.chunking.chunk_size,
                    chunk_overlap=self.config.chunking.chunk_overlap
                )
                all_nodes = splitter.get_nodes_from_documents(documents)

            logger.info(f"Создано {len(all_nodes)} узлов (чанков)")

            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            self.index = VectorStoreIndex(
                nodes=all_nodes,
                storage_context=storage_context,
                show_progress=True
            )
        else:
            logger.info(f"Использование существующей коллекции: {self.config.qdrant_collection}")
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            self.index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store,
                storage_context=storage_context
            )

            try:
                docstore = self.index.docstore
                all_nodes = list(docstore.docs.values())
                logger.info(f"Загружено {len(all_nodes)} узлов из docstore")
            except Exception as e:
                logger.warning(f"Не удалось загрузить узлы для BM25: {e}")

        vector_retriever = self.index.as_retriever(similarity_top_k=self.config.retrieval.overfetch_k)

        if self.config.retrieval.mode == "hybrid":
            if not all_nodes:
                logger.warning("Нет узлов для BM25. Использую только векторный поиск.")
                self.retriever = vector_retriever
            else:
                logger.info("Создание BM25 ретривера...")
                try:
                    bm25_retriever = BM25Retriever.from_defaults(
                        nodes=all_nodes,
                        similarity_top_k=self.config.retrieval.overfetch_k
                    )

                    self.retriever = QueryFusionRetriever(
                        retrievers=[vector_retriever, bm25_retriever],
                        similarity_top_k=self.config.retrieval.overfetch_k,
                        num_queries=1,
                        use_async=False,
                        verbose=True
                    )
                    logger.info("Гибридный ретривер создан")
                except Exception as e:
                    logger.error(f"Ошибка создания гибридного ретривера: {e}")
                    self.retriever = vector_retriever
        else:
            self.retriever = vector_retriever

        self.filtered_retriever = FilteredRetriever(self.retriever, self.df_corpus)

        return self

    def dense_search(self, query: str, top_k: int = 5, exclude_doc_ids: List[int] = None) -> List[Dict]:
        logger.info(f"Плотный поиск: '{query[:100]}...'")

        temp_retriever = self.index.as_retriever(similarity_top_k=top_k + len(exclude_doc_ids or []))
        nodes = temp_retriever.retrieve(query)

        results = self._format_results(nodes, exclude_doc_ids,
                                      self.config.retrieval.overfetch_k if self.config.retrieval.use_reranker else top_k)

        if self.config.retrieval.use_reranker and self.reranker and len(results) > top_k:
            results = rerank_results(query, results, self.reranker, top_k)
        else:
            results = results[:top_k]
        
        return results

    def hybrid_search(self, query: str, top_k: int = 5, exclude_doc_ids: List[int] = None) -> List[Dict]:
        logger.info(f"Гибридный поиск: '{query[:100]}...'")

        if self.config.retrieval.mode != "hybrid":
            logger.info("Гибридный режим не настроен. Использую плотный поиск")
            return self.dense_search(query, top_k, exclude_doc_ids)

        nodes = self.retriever.retrieve(query)
        results = self._format_results(nodes, exclude_doc_ids,
                                      self.config.retrieval.overfetch_k if self.config.retrieval.use_reranker else top_k)

        if self.config.retrieval.use_reranker and self.reranker and len(results) > top_k:
            results = rerank_results(query, results, self.reranker, top_k)
        else:
            results = results[:top_k]
        
        return results

    def filtered_search(self, query: str, hubs: List[str] = None, tags: List[str] = None,
                       top_k: int = 5, exclude_doc_ids: List[int] = None) -> List[Dict]:
        logger.info(f"Поиск с фильтрацией: '{query[:100]}...'")
        logger.info(f"Фильтры - hubs: {hubs}, tags: {tags}")

        filters = {}
        if hubs:
            filters['hubs'] = hubs
        if tags:
            filters['tags'] = tags

        if not filters:
            return self.hybrid_search(query, top_k, exclude_doc_ids)

        query_bundle = QueryBundle(query)
        query_bundle.filters = filters

        nodes = self.filtered_retriever.retrieve(query_bundle)
        results = self._format_results(nodes, exclude_doc_ids,
                                      self.config.retrieval.overfetch_k if self.config.retrieval.use_reranker else top_k)

        if self.config.retrieval.use_reranker and self.reranker and len(results) > top_k:
            results = rerank_results(query, results, self.reranker, top_k)
        else:
            results = results[:top_k]
        
        return results

    def bm25_search(self, query: str, top_k: int = 5, exclude_doc_ids: List[int] = None) -> List[Dict]:
        logger.info(f"BM25 поиск: '{query[:100]}...'")

        try:
            docstore = self.index.docstore
            all_nodes = list(docstore.docs.values())
        except Exception as e:
            logger.error(f"Не удалось загрузить узлы для BM25: {e}")
            return []

        bm25_retriever = BM25Retriever.from_defaults(
            nodes=all_nodes,
            similarity_top_k=top_k + len(exclude_doc_ids or [])
        )

        nodes = bm25_retriever.retrieve(query)
        return self._format_results(nodes, exclude_doc_ids, top_k)

    def _format_results(self, nodes: List[NodeWithScore], exclude_doc_ids: List[int] = None,
                       top_k: int = None) -> List[Dict]:
        exclude_ids = set(str(d) for d in (exclude_doc_ids or []))
        results = []
        seen_doc_ids = set()

        for node in nodes:
            doc_id = node.metadata.get('doc_id')
            if doc_id is None:
                continue

            doc_id_str = str(doc_id)

            if doc_id_str in exclude_ids:
                continue

            if doc_id_str in seen_doc_ids:
                continue

            seen_doc_ids.add(doc_id_str)

            url = node.metadata.get('url', '')
            if not url and 'url' in self.df_corpus.columns:
                try:
                    doc_info = self.df_corpus[self.df_corpus['doc_id'].astype(str) == doc_id_str]
                    if not doc_info.empty:
                        url = doc_info.iloc[0].get('url', '')
                except:
                    pass

            result = {
                'doc_id': doc_id,
                'title': node.metadata.get('title', ''),
                'text': node.text,
                'url': url,
                'score': node.score if hasattr(node, 'score') else None,
                'chunk_text': node.text[:200] + '...' if len(node.text) > 200 else node.text
            }

            if 'hubs' in node.metadata:
                result['hubs'] = node.metadata['hubs']
            if 'tags' in node.metadata:
                result['tags'] = node.metadata['tags']

            results.append(result)

            if top_k and len(results) >= top_k:
                break

        return results


def initialize_search_engines(df_corpus: pd.DataFrame):
    search_engines = {}

    df_processed = df_corpus.copy()

    if 'doc_id' not in df_processed.columns:
        logger.info("Создание doc_id из индекса...")
        df_processed['doc_id'] = df_processed.index

    if 'text' in df_processed.columns:
        initial_len = len(df_processed)
        mask = df_processed['text'].notna() & (df_processed['text'].astype(str).str.strip() != '')
        df_processed = df_processed[mask]
        if len(df_processed) < initial_len:
            logger.info(f"Удалено {initial_len - len(df_processed)} строк с пустым текстом")

    if df_processed.empty:
        logger.error("Нет данных для индексации")
        return search_engines

    for col in ['hubs', 'tags']:
        if col in df_processed.columns:
            logger.info(f"Обработка колонки {col}...")
            try:
                df_processed[col] = df_processed[col].apply(_parse_list_field)
            except Exception as e:
                logger.error(f"Ошибка при обработке {col}: {e}")
                df_processed[col] = [[] for _ in range(len(df_processed))]
        else:
            logger.warning(f"Колонка {col} отсутствует, создаю пустую")
            df_processed[col] = [[] for _ in range(len(df_processed))]

    logger.info(f"Данные готовы: {len(df_processed)} документов")

    configs = [
        ('dense', cfg_matryoshka, "Плотный поиск"),
        ('hybrid', cfg_hybrid_only, "Гибридный поиск"),
        ('rerank', cfg_rerank_only, "Поиск с реранжированием"),
        ('full', cfg_hybrid_rerank, "Полный поиск (гибрид + реранжирование)")
    ]

    for name, config, description in configs:
        logger.info(f"Инициализация {description}...")
        logger.info(f"Коллекция: {config.qdrant_collection}")
        try:
            engine = SearchEngine(df_processed, config)
            engine.build(load_llm=False)
            search_engines[name] = engine
            logger.info(f"{description} готов")
        except Exception as e:
            logger.error(f"Ошибка инициализации {description}: {e}")
            import traceback
            traceback.print_exc()

    return search_engines


class SearchEngineManager:
    _instance = None
    _engines = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def initialize(self, csv_path: str = 'docs_cleaned.csv', limit: Optional[int] = None, force: bool = False):
        if force and self._engines is not None:
            logger.info("Принудительная переинициализация...")
            self._engines = None

        if self._engines is not None:
            logger.info("Движки уже инициализированы, пропускаем")
            return self._engines
        
        if not Path(csv_path).exists():
            raise FileNotFoundError(f"CSV файл не найден: {csv_path}")
        
        logger.info(f"Загрузка данных из {csv_path}")
        df = pd.read_csv(csv_path)
        
        if limit is not None:
            df = df[:limit]
            logger.info(f"Ограничение данных: {limit} документов")
        
        if 'hubs' in df.columns:
            df['hubs'] = df['hubs'].apply(ast.literal_eval)
        if 'tags' in df.columns:
            df['tags'] = df['tags'].apply(ast.literal_eval)
        if 'doc_id' in df.columns:
            df['doc_id'] = df['doc_id'].astype(int)
        else:
            df['doc_id'] = df.index
        
        self._engines = initialize_search_engines(df)
        return self._engines
    
    def get_engine(self, engine_name: str = 'hybrid'):
        if self._engines is None:
            self.initialize()
        return self._engines.get(engine_name)
    
    def search(self, query: str, engine_name: str = 'hybrid', 
               top_k: int = 5, **kwargs) -> List[Dict]:
        engine = self.get_engine(engine_name)
        if not engine:
            logger.error(f"Движок {engine_name} не найден")
            return []
        
        if kwargs.get('hubs') or kwargs.get('tags'):
            return engine.filtered_search(
                query=query,
                hubs=kwargs.get('hubs'),
                tags=kwargs.get('tags'),
                top_k=top_k,
                exclude_doc_ids=kwargs.get('exclude_doc_ids')
            )
        else:
            if engine_name in ['full', 'hybrid']:
                return engine.hybrid_search(query, top_k, kwargs.get('exclude_doc_ids'))
            else:
                return engine.dense_search(query, top_k, kwargs.get('exclude_doc_ids'))
    
    def get_available_engines(self) -> List[str]:
        if self._engines is None:
            return []
        return list(self._engines.keys())
    
    def clear_all_cache(self):
        unload_embedder()
        unload_llm()
        unload_reranker()
        logger.info("Весь кэш моделей очищен")