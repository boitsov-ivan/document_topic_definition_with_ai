from aiogram import Router
from .start import router as start_router
from .upload_doc import router as upload_router



router = Router()

router.include_router(start_router)
router.include_router(upload_router)


__all__ = ['router']