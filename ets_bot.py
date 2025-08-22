#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chatbot ETS Avanzado para Webhook (Render)
Versión completa y mejorada
"""

import logging
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ----------------- CONFIGURACIÓN -----------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Estados para conversación
(ASKING_AGE, ASKING_GENDER, SYMPTOM_DETAIL, FEEDBACK_RATING) = range(4)

# ----------------- SESIONES -----------------
class UserSessionManager:
    def __init__(self):
        self.sessions = {}
        self.user_data = {}
    
    def get_session(self, user_id):
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                'started_at': datetime.now(),
                'current_flow': None,
                'interaction_count': 0
            }
        return self.sessions[user_id]
    
    def update_session(self, user_id, data):
        session = self.get_session(user_id)
        session.update(data)
        session['interaction_count'] += 1
    
    def get_user_data(self, user_id):
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                'age': None,
                'gender': None,
                'risk_level': 'unknown',
                'last_symptoms': []
            }
        return self.user_data[user_id]

# ----------------- CHATBOT -----------------
class ETSBotAdvanced:
    def __init__(self, token):
        self.token = token
        self.application = ApplicationBuilder().token(token).build()
        self.session_manager = UserSessionManager()

        # Base de ETS simplificada
        self.ets_info = {
            "clamidia": {"nombre": "Clamidia", "sintomas": "Secreción anormal, dolor al orinar, dolor abdominal", "info": "Infección bacteriana tratable."},
            "gonorrea": {"nombre": "Gonorrea", "sintomas": "Secreción purulenta, dolor al orinar", "info": "Infección bacteriana, requiere antibióticos."},
            "herpes": {"nombre": "Herpes genital", "sintomas": "Ampollas dolorosas, picazón, ardor", "info": "Infección viral crónica."},
            "vph": {"nombre": "VPH", "sintomas": "Verrugas genitales, a menudo asintomático", "info": "Virus común, algunas cepas causan cáncer."}
        }

        # Centros médicos de ejemplo
        self.medical_centers = {
            "ciudad_mexico": [
                {"nombre": "Clínica Condesa", "direccion": "Av. Insurgentes Sur 136, Roma Norte", "telefono": "55-4114-4000"},
                {"nombre": "Centro de Salud Del Valle", "direccion": "Av. Universidad 1321, Del Valle", "telefono": "55-5534-3428"}
            ]
        }

        # Handlers
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("start", self.start)],
            states={
                ASKING_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_age)],
                ASKING_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_gender)],
                SYMPTOM_DETAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_symptoms)],
                FEEDBACK_RATING: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_feedback)]
            },
            fallbacks=[CommandHandler("cancelar", self.cancel_conversation)]
        )

        self.application.add_handler(conv_handler)
        self.application.add_handler(CommandHandler("ayuda", self.help_command))
        self.application.add_handler(CommandHandler("emergencia", self.emergency))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

    # ----------------- MENÚ -----------------
    def get_main_menu(self):
        keyboard = [
            [InlineKeyboardButton("🔍 Evaluación de síntomas", callback_data="symptoms")],
            [InlineKeyboardButton("📚 Info ETS", callback_data="info")],
            [InlineKeyboardButton("🏥 Centros Médicos", callback_data="centers")],
            [InlineKeyboardButton("🆘 Emergencia", callback_data="emergency")]
        ]
        return InlineKeyboardMarkup(keyboard)

    # ----------------- COMANDOS -----------------
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_id = user.id
        self.session_manager.update_session(user_id, {'current_flow': 'main_menu'})

        welcome_text = f"""
🏥 **¡Hola {user.first_name}!** Bienvenido/a al asistente de salud sexual.

🔒 Privacidad garantizada
⚠️ No reemplaza consulta médica
🆘 En emergencias, llama a 911

Primero, necesito conocer algunos datos para personalizar la experiencia.
¿Cuál es tu edad?
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        return ASKING_AGE

    async def collect_age(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        try:
            age = int(update.message.text.strip())
            if 13 <= age <= 100:
                self.session_manager.get_user_data(user_id)['age'] = age
                text = "✅ Edad registrada.\n¿Cuál es tu género? (Masculino, Femenino, Otro)"
                await update.message.reply_text(text)
                return ASKING_GENDER
            else:
                await update.message.reply_text("⚠️ Edad inválida. Ingresa un número entre 13 y 100.")
                return ASKING_AGE
        except ValueError:
            await update.message.reply_text("⚠️ Ingresa solo números para la edad.")
            return ASKING_AGE

    async def collect_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        self.session_manager.get_user_data(user_id)['gender'] = update.message.text.strip()
        text = "✅ Género registrado.\nAhora, describe tus síntomas o preocupaciones:"
        await update.message.reply_text(text)
        return SYMPTOM_DETAIL

    async def collect_symptoms(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        symptoms = update.message.text.lower()
        user_data = self.session_manager.get_user_data(user_id)
        user_data['last_symptoms'] = [symptoms]

        analysis = self.analyze_symptoms(symptoms)
        user_data['risk_level'] = analysis['risk_level']

        response = f"""
🔍 **Análisis de síntomas**

{analysis['assessment']}

**Recomendaciones:**
{analysis['recommendations']}

**Posibles condiciones:**
{analysis['possible_conditions']}
        """
        await update.message.reply_text(response, parse_mode='Markdown', reply_markup=self.get_main_menu())
        return ConversationHandler.END

    def analyze_symptoms(self, text):
        found = []
        if any(w in text for w in ['dolor', 'duele']):
            found.append('dolor')
        if any(w in text for w in ['secreción', 'flujo']):
            found.append('secrecion')
        if any(w in text for w in ['ampolla', 'llaga']):
            found.append('lesiones')

        score = len(found)
        if score >= 3:
            risk = 'high'
        elif score == 2:
            risk = 'medium'
        else:
            risk = 'low'

        assessment = {
            'high': '🔴 Riesgo alto. Consulta médica urgente.',
            'medium': '🟡 Riesgo moderado. Considera hacerte pruebas.',
            'low': '🟢 Riesgo bajo. Mantén hábitos seguros.'
        }[risk]

        recommendations = "• Consulta médica\n• Pruebas de ETS"
        possible_conditions = ", ".join(found) if found else "Evaluación médica necesaria"

        return {'risk_level': risk, 'assessment': assessment, 'recommendations': recommendations, 'possible_conditions': possible_conditions}

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "symptoms":
            await query.edit_message_text("Describe tus síntomas con tus propias palabras:", reply_markup=None)
        elif query.data == "info":
            text = "📚 Selecciona la ETS:"
            keyboard = [[InlineKeyboardButton(ets['nombre'], callback_data=f"info_{key}")] for key, ets in self.ets_info.items()]
            keyboard.append([InlineKeyboardButton("⬅️ Volver", callback_data="menu")])
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        elif query.data.startswith("info_"):
            key = query.data.replace("info_", "")
            ets = self.ets_info.get(key)
            if ets:
                text = f"📋 **{ets['nombre']}**\nSíntomas: {ets['sintomas']}\nInfo: {ets['info']}"
                keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data="info")]]
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        elif query.data == "centers":
            text = "🏥 Centros Médicos disponibles:\n"
            for c in self.medical_centers.get("ciudad_mexico", []):
                text += f"{c['nombre']} - {c['direccion']} - {c['telefono']}\n"
            await query.edit_message_text(text, reply_markup=self.get_main_menu())
        elif query.data == "emergency":
            await query.edit_message_text("🆘 En caso de emergencia, llama al 911.", reply_markup=self.get_main_menu())
        elif query.data == "menu":
            await query.edit_message_text("🏥 Menú Principal", reply_markup=self.get_main_menu())

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = "ℹ️ Ayuda: Usa los menús para orientación sobre ETS y salud sexual."
        await update.message.reply_text(text, reply_markup=self.get_main_menu())

    async def emergency(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = "🆘 Contacta servicios médicos si tienes síntomas graves. Emergencias: 911"
        await update.message.reply_text(text, reply_markup=self.get_main_menu())

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Usa el menú para orientación.", reply_markup=self.get_main_menu())

    async def collect_feedback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("¡Gracias por tu feedback!")

    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Conversación cancelada.", reply_markup=self.get_main_menu())
        return ConversationHandler.END

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
    bot = ETSBotAdvanced(TOKEN)
    bot.run_webhook()

if __name__ == "__main__":
    main()
