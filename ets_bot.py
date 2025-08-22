#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chatbot ETS Completo para Webhook (Render)
"""

import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
TOKEN = os.environ.get("TELEGRAM_TOKEN")  # token de Telegram
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # URL pública de Render

class ETSBotSimple:
    def __init__(self, token):
        self.token = token
        self.application = ApplicationBuilder().token(token).build()

        # Base de conocimientos simplificada
        self.ets_info = {
            "clamidia": {
                "nombre": "Clamidia",
                "sintomas": "Secreción anormal, dolor al orinar, dolor abdominal",
                "info": "Infección bacteriana común, fácilmente tratable con antibióticos."
            },
            "gonorrea": {
                "nombre": "Gonorrea",
                "sintomas": "Secreción purulenta, dolor intenso al orinar",
                "info": "Infección bacteriana que requiere tratamiento antibiótico específico."
            },
            "herpes": {
                "nombre": "Herpes Genital",
                "sintomas": "Ampollas dolorosas, picazón, ardor",
                "info": "Infección viral crónica, manejable con medicamentos antivirales."
            },
            "vph": {
                "nombre": "VPH",
                "sintomas": "Verrugas genitales, a menudo asintomático",
                "info": "Virus común, algunas cepas pueden causar cáncer. Vacuna disponible."
            }
        }

        # Configurar handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("ayuda", self.help_command))
        self.application.add_handler(CommandHandler("emergencia", self.emergency))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

    # ----------------- MENÚS Y RESPUESTAS -----------------
    def get_main_menu(self):
        keyboard = [
            [InlineKeyboardButton("🔍 Evaluar Síntomas", callback_data="symptoms")],
            [InlineKeyboardButton("📚 Info sobre ETS", callback_data="info")],
            [InlineKeyboardButton("💬 Hacer Pregunta", callback_data="question")],
            [InlineKeyboardButton("🏥 Centros Médicos", callback_data="centers")],
            [InlineKeyboardButton("🆘 Emergencia", callback_data="emergency")]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        welcome_text = f"""
🏥 **¡Hola {user.first_name}!** 

Soy tu asistente de salud sexual confidencial.

🔒 **Privacidad garantizada**
⚠️ **No reemplazo consulta médica**
🆘 **En emergencia: contacta servicios médicos**

¿Cómo puedo ayudarte?
        """
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=self.get_main_menu()
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
ℹ️ **Ayuda - Asistente de Salud Sexual**

**Comandos:**
• /start - Iniciar
• /ayuda - Esta ayuda
• /emergencia - Info de emergencia

**Funciones:**
🔍 Evaluar síntomas
📚 Información sobre ETS
💬 Preguntas libres
🏥 Centros médicos

**Importante:**
• Información confidencial
• No reemplaza consulta médica
• En emergencia: busca ayuda inmediata
        """
        await update.message.reply_text(help_text, parse_mode='Markdown', reply_markup=self.get_main_menu())

    async def emergency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = """
🆘 **INFORMACIÓN DE EMERGENCIA**

**Números de emergencia México:**
• 911 - Emergencias
• 065 - Cruz Roja
• Locatel: 56-58-1111

🚨 Busca atención médica inmediata si tienes síntomas graves.
        """
        await update.message.reply_text(text, parse_mode='Markdown')

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        if query.data == "symptoms":
            await self.show_symptom_eval(query)
        elif query.data == "info":
            await self.show_ets_info(query)
        elif query.data == "question":
            await self.show_question_mode(query)
        elif query.data == "centers":
            await self.show_medical_centers(query)
        elif query.data == "emergency":
            await self.show_emergency(query)
        elif query.data == "menu":
            await self.show_main_menu_callback(query)
        elif query.data.startswith("info_"):
            await self.show_specific_ets(query, query.data.replace("info_", ""))

    async def show_symptom_eval(self, query):
        text = """
🔍 **Evaluación de Síntomas**

Describe tus síntomas con tus propias palabras.

⚠️ Esta evaluación es orientativa, no reemplaza consulta médica.
        """
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="menu")]])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)

    async def show_ets_info(self, query):
        text = "📚 **Información sobre ETS**\nSelecciona la enfermedad:"
        keyboard = [[InlineKeyboardButton(f"📋 {ets['nombre']}", callback_data=f"info_{key}")] for key, ets in self.ets_info.items()]
        keyboard.append([InlineKeyboardButton("⬅️ Volver", callback_data="menu")])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_specific_ets(self, query, ets_key):
        ets = self.ets_info.get(ets_key)
        if not ets:
            await query.edit_message_text("Información no encontrada.")
            return
        text = f"""
📋 **{ets['nombre']}**

**Síntomas comunes:**
{ets['sintomas']}

**Información:**
{ets['info']}

**Importante:** Solo un médico puede dar diagnóstico definitivo.
        """
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📚 Volver a Info ETS", callback_data="info")],
            [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu")]
        ])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)

    async def show_question_mode(self, query):
        text = """
💬 **Pregunta Libre**

Puedes preguntarme sobre:
• Prevención de ETS
• Métodos de protección
• Cuándo hacerse pruebas
• Dudas generales sobre salud sexual
        """
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="menu")]])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)

    async def show_medical_centers(self, query):
        text = """
🏥 **Centros Médicos**

Dónde hacerse pruebas:
• Centros de Salud públicos
• Clínicas especializadas  
• Laboratorios privados
• Hospitales

📞 Emergencia: 911
        """
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="menu")]])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)

    async def show_emergency(self, query):
        text = "🆘 Contacta servicios médicos si presentas síntomas graves o urgentes."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="menu")]])
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)

    async def show_main_menu_callback(self, query):
        text = "🏥 **Menú Principal**\n¿En qué puedo ayudarte hoy?"
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=self.get_main_menu())

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.lower()

        # Análisis completo de síntomas
        if any(word in text for word in ['dolor', 'duele', 'molestia']):
            response = """
⚠️ **Síntomas de Dolor**

Dolor al orinar puede indicar:
• Infección del tracto urinario
• Clamidia o gonorrea
• Otras infecciones

Recomendación:
🏥 Consulta médica
🧪 Considera hacerte pruebas de ETS
💊 No te automediques
            """
        elif any(word in text for word in ['secreción', 'flujo', 'líquido']):
            response = """
⚠️ **Secreción Anormal**

Puede indicar:
• Clamidia, gonorrea
• Tricomoniasis
• Infecciones por hongos

Consulta médica pronto.
            """
        elif any(word in text for word in ['picazón', 'comezón', 'pica']):
            response = """
⚠️ **Picazón Genital**

Posibles causas:
• Infecciones por hongos
• Herpes genital
• Reacciones alérgicas

Consulta médica y mantén higiene adecuada.
            """
        elif any(word in text for word in ['ampolla', 'llaga', 'herida']):
            response = """
⚠️ **Lesiones Genitales**

Pueden indicar:
• Herpes genital
• Sífilis
• VPH (verrugas)

Consulta médica urgente.
            """
        elif any(word in text for word in ['prevenir', 'prevención', 'evitar']):
            response = """
🛡️ **Prevención de ETS**

• Uso correcto de preservativos
• Reducir número de parejas
• Pruebas regulares
• Vacunación (VPH, Hepatitis B)
• Comunicación con parejas
            """
        elif any(word in text for word in ['prueba', 'test', 'examen']):
            response = """
🔬 **Pruebas de ETS**

Tipos de pruebas:
• Sangre (VIH, sífilis)
• Orina (clamidia, gonorrea)
• Hisopado (herpes, VPH)

Cuándo hacerse pruebas:
• Anualmente si eres sexualmente activo
• Antes de nueva relación
• Si tienes síntomas
            """
        else:
            response = """
💬 Te ayudo con información sobre salud sexual y ETS.
Usa los menús para orientación detallada.
⚠️ Recuerda: consulta siempre un médico para diagnóstico definitivo.
            """

        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=self.get_main_menu())

    # ----------------- EJECUCIÓN -----------------
    def run_webhook(self):
        port = int(os.environ.get("PORT", 5000))
        self.application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
        )

def main():
    bot = ETSBotSimple(TOKEN)
    bot.run_webhook()

if __name__ == "__main__":
    main()
