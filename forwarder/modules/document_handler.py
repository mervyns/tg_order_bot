import asyncio
from typing import Optional, Tuple, Union
import PyPDF2
import io
from PIL import Image
import pytesseract
from abc import ABC, abstractmethod

from telegram import Update, Message
from telegram.ext import MessageHandler, filters, ContextTypes
from forwarder import LOGGER, get_bot

class DocumentProcessor(ABC):
    """Abstract base class for document processors"""
    
    @abstractmethod
    async def can_process(self, message: Message) -> bool:
        """Check if this processor can handle the document"""
        pass
        
    @abstractmethod
    async def process(self, update: Update) -> str:
        """Process the document and return the extracted text"""
        pass

    async def download_file(self, message: Message) -> Optional[bytes]:
        """Download file from Telegram message"""
        try:
            file = await message.document.get_file()
            return await file.download_as_bytearray()
        except Exception as e:
            LOGGER.error(f"Error downloading file: {e}")
            return None

    async def format_response(self, text: str, info: str) -> str:
        """Format text for Telegram message with length limit"""
        header = f"📄 {info}\n\n"
        max_length = 4000 - len(header)
        
        if len(text) > max_length:
            return header + text[:max_length] + "\n\n... [Text truncated due to length]"
        return header + text

class PDFProcessor(DocumentProcessor):
    """Processor for PDF documents"""
    
    async def can_process(self, message: Message) -> bool:
        return message.document.mime_type == 'application/pdf'
    
    async def extract_text(self, pdf_bytes: bytes) -> Tuple[str, int]:
        """Extract text from PDF bytes"""
        pdf_file = io.BytesIO(pdf_bytes)
        reader = PyPDF2.PdfReader(pdf_file)
        
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n\n"
        
        return text.strip(), len(reader.pages)
    
    async def process(self, update: Update) -> str:
        try:
            pdf_bytes = await self.download_file(update.message)
            if not pdf_bytes:
                return "❌ Failed to download PDF"
                
            text, page_count = await self.extract_text(pdf_bytes)
            if not text:
                return "❌ No text could be extracted from this PDF"
                
            info = f"PDF Contents ({page_count} {'page' if page_count == 1 else 'pages'})"
            return await self.format_response(text, info)
            
        except Exception as e:
            LOGGER.error(f"Error processing PDF: {e}")
            return f"❌ Error processing PDF: {str(e)}"

class ImageProcessor(DocumentProcessor):
    """Processor for image documents"""
    
    SUPPORTED_TYPES = {'image/jpeg', 'image/png', 'image/tiff'}
    
    async def can_process(self, message: Message) -> bool:
        return message.document.mime_type in self.SUPPORTED_TYPES
    
    async def extract_text(self, image_bytes: bytes) -> str:
        """Extract text from image using OCR"""
        image = Image.open(io.BytesIO(image_bytes))
        return pytesseract.image_to_string(image)
    
    async def process(self, update: Update) -> str:
        try:
            image_bytes = await self.download_file(update.message)
            if not image_bytes:
                return "❌ Failed to download image"
                
            text = await self.extract_text(image_bytes)
            if not text.strip():
                return "❌ No text could be extracted from this image"
                
            return await self.format_response(text, "Extracted Text from Image")
            
        except Exception as e:
            LOGGER.error(f"Error processing image: {e}")
            return f"❌ Error processing image: {str(e)}"

class DocumentHandler:
    """Main handler for all document types"""
    
    def __init__(self):
        self.processors = [
            PDFProcessor(),
            ImageProcessor()
        ]
    
    async def process_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process incoming documents"""
        if not update.message or not update.message.document:
            return
            
        try:
            # Send initial processing message
            status_message = await update.message.reply_text("Processing document... 🔄")
            
            # Find suitable processor
            for processor in self.processors:
                if await processor.can_process(update.message):
                    result = await processor.process(update)
                    await status_message.edit_text(result)
                    return
                    
            # No suitable processor found
            await status_message.edit_text("❌ Unsupported document type. Please send a PDF or image file.")
            
        except Exception as e:
            LOGGER.error(f"Error in document handler: {e}")
            if 'status_message' in locals():
                await status_message.edit_text(
                    "❌ An error occurred while processing your document. Please try again."
                )

# Create handler instance
document_handler = DocumentHandler()

# Register handler for documents in private chats
DOCUMENT_HANDLER = MessageHandler(
    filters.ChatType.PRIVATE & filters.Document.ALL,
    document_handler.process_document
)

def register_handlers():
    """Register handlers with the bot"""
    bot = get_bot()
    bot.add_handler(DOCUMENT_HANDLER)
    LOGGER.info("Document handlers registered successfully")