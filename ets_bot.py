#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chatbot ETS Avanzado para Webhook (Render)
Versión mejorada con funcionalidades avanzadas
"""

import logging
import os
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# Configurar logging más detallado
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# Estados para conversaciones
(ASKING_AGE, ASKING_GENDER, SYMPTOM_DETAIL, RISK_ASSESSMENT, 
 APPOINTMENT_BOOKING, FEEDBACK_RATING) = range(6)

class UserSessionManager:
    """Gestiona las sesiones de usuario en memoria"""
    def __init__(self):
        self.sessions = {}
        self.user_data = {}
    
    def get_session(self, user_id: int) -> Dict:
        if user_id not in self.sessions:
            self.sessions[user_id] = {
                'started_at': datetime.now(),
                'current_flow': None,
                'context': {},
                'interaction_count': 0
            }
        return self.sessions[user_id]
    
    def update_session(self, user_id: int, data: Dict):
        session = self.get_session(user_id)
        session.update(data)
        session['interaction_count'] += 1
    
    def get_user_data(self, user_id: int) -> Dict:
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                'age': None,
                'gender': None,
                'risk_level': 'unknown',
                'last_symptoms': [],
                'preferences': {},
                'language': 'es'
            }
        return self.user_data[user_id]

class ETSBotAdvanced:
    def __init__(self, token):
        self.token = token
        self.application = ApplicationBuilder().token(token).build()
        self.session_manager = UserSessionManager()

        # Base de conocimientos expandida y estructurada
        self.ets_database = {
            "clamidia": {
                "nombre": "Clamidia",
                "tipo": "bacteriana",
                "prevalencia": "alta",
                "sintomas": {
                    "comunes": ["secreción anormal", "dolor al orinar", "dolor pélvico"],
                    "hombres": ["secreción del pene", "dolor testicular"],
                    "mujeres": ["sangrado entre períodos", "dolor durante relaciones"],
                    "asintomatico": 70
                },
                "info": "Infección bacteriana muy común y fácilmente tratable con antibióticos.",
                "tratamiento": "Antibióticos (azitromicina o doxiciclina)",
                "prevencion": ["preservativos", "pruebas regulares", "pareja única"],
                "tiempo_sintomas": "1-3 semanas después de exposición",
                "complicaciones": ["EIP", "infertilidad", "embarazo ectópico"]
            },
            "gonorrea": {
                "nombre": "Gonorrea",
                "tipo": "bacteriana",
                "prevalencia": "alta",
                "sintomas": {
                    "comunes": ["secreción purulenta", "dolor intenso al orinar"],
                    "hombres": ["secreción amarilla-verdosa del pene"],
                    "mujeres": ["sangrado vaginal anormal", "dolor pélvico"],
                    "asintomatico": 50
                },
                "info": "Infección bacteriana que puede causar resistencia a antibióticos.",
                "tratamiento": "Antibióticos específicos (ceftriaxona + azitromicina)",
                "prevencion": ["preservativos", "pruebas regulares"],
                "tiempo_sintomas": "2-7 días después de exposición",
                "complicaciones": ["EIP", "artritis", "problemas cardíacos"]
            },
            "herpes": {
                "nombre": "Herpes Genital (HSV-1/HSV-2)",
                "tipo": "viral",
                "prevalencia": "muy alta",
                "sintomas": {
                    "comunes": ["ampollas dolorosas", "picazón", "ardor", "fiebre"],
                    "primer_brote": ["síntomas similares a gripe", "ganglios inflamados"],
                    "recurrencias": ["síntomas más leves", "duración menor"],
                    "asintomatico": 80
                },
                "info": "Infección viral crónica con brotes recurrentes, manejable con antivirales.",
                "tratamiento": "Antivirales (aciclovir, valaciclovir)",
                "prevencion": ["preservativos", "evitar contacto durante brotes"],
                "tiempo_sintomas": "2-12 días después de exposición",
                "complicaciones": ["recurrencias frecuentes", "transmisión neonatal"]
            },
            "vph": {
                "nombre": "Virus del Papiloma Humano (VPH)",
                "tipo": "viral",
                "prevalencia": "muy alta",
                "sintomas": {
                    "comunes": ["verrugas genitales", "a menudo asintomático"],
                    "alto_riesgo": ["cambios cervicales", "sin síntomas visibles"],
                    "bajo_riesgo": ["verrugas genitales visibles"],
                    "asintomatico": 90
                },
                "info": "Virus muy común, algunas cepas pueden causar cáncer cervical.",
                "tratamiento": "Tratamiento de verrugas, seguimiento médico",
                "prevencion": ["vacuna VPH", "preservativos", "Papanicolaou regular"],
                "tiempo_sintomas": "semanas a años después de exposición",
                "complicaciones": ["cáncer cervical", "cáncer genital"]
            },
            "sifilis": {
                "nombre": "Sífilis",
                "tipo": "bacteriana",
                "prevalencia": "media",
                "sintomas": {
                    "primaria": ["chancro indoloro", "una lesión"],
                    "secundaria": ["erupción", "fiebre", "ganglios inflamados"],
                    "latente": ["sin síntomas visibles"],
                    "terciaria": ["daño a órganos", "problemas neurológicos"],
                    "asintomatico": 30
                },
                "info": "Infección bacteriana que progresa en etapas si no se trata.",
                "tratamiento": "Penicilina",
                "prevencion": ["preservativos", "pruebas regulares"],
                "tiempo_sintomas": "10-90 días después de exposición",
                "complicaciones": ["daño neurológico", "problemas cardíacos", "muerte"]
            }
        }

        # Sistema de evaluación de riesgo
        self.risk_factors = {
            'high': {
                'keywords': ['múltiples parejas', 'sin preservativo', 'síntomas graves', 'fiebre'],
                'message': '🔴 **RIESGO ALTO** - Se recomienda consulta médica urgente'
            },
            'medium': {
                'keywords': ['nueva pareja', 'síntomas leves', 'exposición reciente'],
                'message': '🟡 **RIESGO MODERADO** - Considera hacerte pruebas pronto'
            },
            'low': {
                'keywords': ['pareja estable', 'uso de preservativo', 'sin síntomas'],
                'message': '🟢 **RIESGO BAJO** - Mantén prácticas seguras'
            }
        }

        # Centros médicos por ubicación (ejemplo México)
        self.medical_centers = {
            "ciudad_mexico": {
                "nombre": "Ciudad de México",
                "centros": [
                    {
                        "nombre": "Clínica Condesa",
                        "direccion": "Av. Insurgentes Sur 136, Roma Norte",
                        "telefono": "55-4114-4000",
                        "servicios": ["Pruebas VIH", "Pruebas ETS completas", "Consulta gratuita"],
                        "horarios": "Lun-Vie 8:00-20:00"
                    },
                    {
                        "nombre": "Centro de Salud T-III Dr. Gustavo A. Rovirosa",
                        "direccion": "Av. Universidad 1321, Del Valle",
                        "telefono": "55-5534-3428",
                        "servicios": ["Consulta general", "Pruebas básicas de ETS"],
                        "horarios": "Lun-Vie 7:00-15:00"
                    }
                ]
            },
            "guadalajara": {
                "nombre": "Guadalajara",
                "centros": [
                    {
                        "nombre": "Clínica de VIH del Hospital Civil",
                        "direccion": "Hospital 278, Guadalajara Centro",
                        "telefono": "33-3614-7043",
                        "servicios": ["Pruebas VIH", "Consulta especializada"],
                        "horarios": "Lun-Vie 8:00-14:00"
                    }
                ]
            }
        }

        # Configurar conversación estructurada
        conv_handler = ConversationHandler(
            entry_points=[
                CallbackQueryHandler(self.start_assessment, pattern="^full_assessment$"),
                CallbackQueryHandler(self.start_appointment, pattern="^book_appointment$")
            ],
            states={
                ASKING_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_age)],
                ASKING_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_gender)],
                SYMPTOM_DETAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_symptoms)],
                RISK_ASSESSMENT: [CallbackQueryHandler(self.handle_risk_callback)],
                APPOINTMENT_BOOKING: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_appointment)],
                FEEDBACK_RATING: [CallbackQueryHandler(self.handle_feedback)]
            },
            fallbacks=[CommandHandler("cancelar", self.cancel_conversation)]
        )

        # Configurar handlers
        self.application.add_handler(conv_handler)
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("perfil", self.profile_command))
        self.application.add_handler(CommandHandler("estadisticas", self.stats_command))
        self.application.add_handler(CommandHandler("ayuda", self.help_command))
        self.application.add_handler(CommandHandler("emergencia", self.emergency))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))
        self.application.add_handler(MessageHandler(filters.LOCATION, self.handle_location))

    # ----------------- MENÚS Y RESPUESTAS MEJORADOS -----------------
    def get_main_menu(self, user_id: int = None):
        user_data = self.session_manager.get_user_data(user_id) if user_id else {}
        
        keyboard = [
            [InlineKeyboardButton("🎯 Evaluación Completa", callback_data="full_assessment")],
            [InlineKeyboardButton("🔍 Síntomas Rápidos", callback_data="quick_symptoms")],
            [InlineKeyboardButton("📚 Enciclopedia ETS", callback_data="encyclopedia")],
            [InlineKeyboardButton("🧪 Guía de Pruebas", callback_data="test_guide")],
            [InlineKeyboardButton("🏥 Encontrar Centros", callback_data="find_centers")],
            [InlineKeyboardButton("📅 Agendar Cita", callback_data="book_appointment")],
            [InlineKeyboardButton("💬 Chat Libre", callback_data="free_chat")],
            [InlineKeyboardButton("⚙️ Mi Perfil", callback_data="profile"), 
             InlineKeyboardButton("🆘 Emergencia", callback_data="emergency")]
        ]
        return InlineKeyboardMarkup(keyboard)

    def get_location_keyboard(self):
        keyboard = [
            [KeyboardButton("📍 Compartir mi ubicación", request_location=True)],
            [KeyboardButton("🏙️ Ciudad de México"), KeyboardButton("🌆 Guadalajara")],
            [KeyboardButton("🏘️ Monterrey"), KeyboardButton("🏖️ Cancún")],
            [KeyboardButton("❌ Cancelar")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        user_id = user.id
        
        # Actualizar sesión
        self.session_manager.update_session(user_id, {'current_flow': 'main_menu'})
        
        welcome_text = f"""
🏥 **¡Hola {user.first_name}!** Bienvenido/a a tu Asistente Inteligente de Salud Sexual

🤖 **Funciones Avanzadas:**
• Evaluación personalizada de síntomas
• Recomendaciones basadas en tu perfil
• Localización de centros médicos
• Seguimiento de tu salud sexual

🔒 **100% Privado y Confidencial**
⚠️ **Complementa, no reemplaza la consulta médica**
🆘 **Emergencias: 911**

*¿Es tu primera vez? Te haré algunas preguntas básicas para personalizar la experiencia.*
        """
        
        # Verificar si es usuario nuevo
        user_data = self.session_manager.get_user_data(user_id)
        if not user_data.get('age'):
            keyboard = [
                [InlineKeyboardButton("✅ Configurar mi perfil", callback_data="setup_profile")],
                [InlineKeyboardButton("⏭️ Saltar por ahora", callback_data="skip_setup")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else:
            reply_markup = self.get_main_menu(user_id)
            
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )

    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        user_data = self.session_manager.get_user_data(user_id)
        session = self.session_manager.get_session(user_id)
        
        profile_text = f"""
👤 **Mi Perfil de Salud Sexual**

**Información básica:**
• Edad: {user_data.get('age', 'No especificada')}
• Género: {user_data.get('gender', 'No especificado')}
• Nivel de riesgo: {user_data.get('risk_level', 'Por evaluar')}

**Actividad:**
• Interacciones: {session.get('interaction_count', 0)}
• Última consulta: {user_data.get('last_symptoms', ['Ninguna'])[0] if user_data.get('last_symptoms') else 'Ninguna'}

**Recomendaciones personalizadas:**
{self.get_personalized_recommendations(user_data)}
        """
        
        keyboard = [
            [InlineKeyboardButton("✏️ Editar perfil", callback_data="edit_profile")],
            [InlineKeyboardButton("📊 Ver estadísticas", callback_data="view_stats")],
            [InlineKeyboardButton("🏠 Menú principal", callback_data="menu")]
        ]
        
        await update.message.reply_text(
            profile_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def get_personalized_recommendations(self, user_data: Dict) -> str:
        age = user_data.get('age', 0)
        risk_level = user_data.get('risk_level', 'unknown')
        
        recommendations = []
        
        if age and age < 25:
            recommendations.append("• Vacuna VPH recomendada")
        if risk_level == 'high':
            recommendations.append("• Pruebas cada 3-6 meses")
        elif risk_level == 'medium':
            recommendations.append("• Pruebas anuales recomendadas")
        else:
            recommendations.append("• Pruebas según actividad sexual")
            
        recommendations.append("• Uso consistente de preservativos")
        
        return "\n".join(recommendations) if recommendations else "• Mantén prácticas sexuales seguras"

    # ----------------- EVALUACIÓN AVANZADA DE SÍNTOMAS -----------------
    async def start_assessment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        user_data = self.session_manager.get_user_data(user_id)
        
        if not user_data.get('age'):
            text = """
📝 **Evaluación Completa de Salud Sexual**

Para brindarte la mejor orientación, necesito conocer algunos datos básicos.

*Esta información es completamente confidencial y se usa solo para personalizar las recomendaciones.*

**Pregunta 1/3:** ¿Cuál es tu edad?
(Escribe solo el número)
            """
            await query.edit_message_text(text, parse_mode='Markdown')
            return ASKING_AGE
        else:
            return await self.start_symptom_collection(query)

    async def collect_age(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        age_text = update.message.text.strip()
        
        try:
            age = int(age_text)
            if 13 <= age <= 100:  # Rango válido
                user_data = self.session_manager.get_user_data(user_id)
                user_data['age'] = age
                
                text = """
✅ **Edad registrada**

**Pregunta 2/3:** ¿Cuál es tu género?

Selecciona una opción o escribe tu respuesta:
                """
                keyboard = [
                    [InlineKeyboardButton("👨 Masculino", callback_data="gender_male")],
                    [InlineKeyboardButton("👩 Femenino", callback_data="gender_female")],
                    [InlineKeyboardButton("🏳️‍⚧️ No binario", callback_data="gender_nonbinary")],
                    [InlineKeyboardButton("✏️ Otro (escribir)", callback_data="gender_other")]
                ]
                await update.message.reply_text(
                    text, 
                    parse_mode='Markdown', 
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                return ASKING_GENDER
            else:
                await update.message.reply_text(
                    "⚠️ Por favor, ingresa una edad válida (13-100 años):"
                )
                return ASKING_AGE
        except ValueError:
            await update.message.reply_text(
                "⚠️ Por favor, ingresa solo números para tu edad:"
            )
            return ASKING_AGE

    async def collect_gender(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            
            gender_map = {
                'gender_male': 'Masculino',
                'gender_female': 'Femenino', 
                'gender_nonbinary': 'No binario',
                'gender_other': 'other_input'
            }
            
            if query.data == 'gender_other':
                await query.edit_message_text(
                    "✏️ **Género personalizado**\n\nEscribe cómo te identificas:"
                )
                return ASKING_GENDER
            else:
                user_data = self.session_manager.get_user_data(user_id)
                user_data['gender'] = gender_map[query.data]
                return await self.start_symptom_collection(query)
        else:
            # Input de texto para género personalizado
            user_data = self.session_manager.get_user_data(user_id)
            user_data['gender'] = update.message.text.strip()
            
            text = "✅ **Perfil configurado**\n\nAhora, describe tus síntomas o preocupaciones:"
            await update.message.reply_text(text, parse_mode='Markdown')
            return SYMPTOM_DETAIL

    async def start_symptom_collection(self, query):
        text = """
✅ **Perfil configurado**

**Pregunta 3/3:** Describe detalladamente tus síntomas o preocupaciones:

Puedes mencionar:
• Síntomas específicos que experimentas
• Cuándo comenzaron
• Situaciones de riesgo recientes
• Cualquier otra preocupación

*Sé lo más específico/a posible para una mejor evaluación.*
        """
        await query.edit_message_text(text, parse_mode='Markdown')
        return SYMPTOM_DETAIL

    async def collect_symptoms(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        symptoms_text = update.message.text.lower()
        
        # Guardar síntomas
        user_data = self.session_manager.get_user_data(user_id)
        user_data['last_symptoms'] = [symptoms_text]
        
        # Análisis inteligente de síntomas
        analysis = self.analyze_symptoms_advanced(symptoms_text, user_data)
        risk_level = analysis['risk_level']
        user_data['risk_level'] = risk_level
        
        response_text = f"""
🔍 **Análisis de Síntomas Completado**

{analysis['assessment']}

**Recomendaciones específicas:**
{analysis['recommendations']}

**Posibles condiciones a considerar:**
{analysis['possible_conditions']}

⚠️ **Importante:** Esta es una evaluación orientativa. Un profesional médico debe hacer el diagnóstico definitivo.
        """
        
        keyboard = [
            [InlineKeyboardButton("🏥 Encontrar centros médicos", callback_data="find_centers")],
            [InlineKeyboardButton("📞 Información de emergencia", callback_data="emergency")],
            [InlineKeyboardButton("📚 Más información", callback_data="encyclopedia")],
            [InlineKeyboardButton("🔄 Nueva evaluación", callback_data="full_assessment")],
            [InlineKeyboardButton("🏠 Menú principal", callback_data="menu")]
        ]
        
        await update.message.reply_text(
            response_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        # Solicitar feedback
        feedback_keyboard = [
            [InlineKeyboardButton("⭐⭐⭐⭐⭐", callback_data="rating_5")],
            [InlineKeyboardButton("⭐⭐⭐⭐", callback_data="rating_4")],
            [InlineKeyboardButton("⭐⭐⭐", callback_data="rating_3")],
            [InlineKeyboardButton("⭐⭐", callback_data="rating_2")],
            [InlineKeyboardButton("⭐", callback_data="rating_1")]
        ]
        
        await update.message.reply_text(
            "💭 **¿Qué tan útil fue esta evaluación?**",
            reply_markup=InlineKeyboardMarkup(feedback_keyboard)
        )
        
        return ConversationHandler.END

    def analyze_symptoms_advanced(self, symptoms_text: str, user_data: Dict) -> Dict:
        """Análisis avanzado de síntomas con ML básico"""
        
        # Palabras clave categorizadas
        symptom_keywords = {
            'dolor': ['dolor', 'duele', 'molestia', 'ardor', 'punzadas'],
            'secrecion': ['secreción', 'flujo', 'líquido', 'descarga', 'supuración'],
            'lesiones': ['ampolla', 'llaga', 'herida', 'úlcera', 'lesión', 'verruga'],
            'picazon': ['picazón', 'comezón', 'prurito', 'pica'],
            'sistemicos': ['fiebre', 'malestar', 'cansancio', 'ganglios', 'dolor de cabeza']
        }
        
        severity_keywords = {
            'high': ['intenso', 'severo', 'grave', 'mucho', 'insoportable', 'sangre'],
            'medium': ['moderado', 'regular', 'intermitente', 'a veces'],
            'low': ['leve', 'poco', 'ligero', 'ocasional']
        }
        
        # Análisis de presencia de síntomas
        found_symptoms = []
        severity_score = 0
        
        for category, keywords in symptom_keywords.items():
            if any(keyword in symptoms_text for keyword in keywords):
                found_symptoms.append(category)
        
        for severity, keywords in severity_keywords.items():
            if any(keyword in symptoms_text for keyword in keywords):
                if severity == 'high':
                    severity_score += 3
                elif severity == 'medium':
                    severity_score += 2
                else:
                    severity_score += 1
        
        # Determinar nivel de riesgo
        if severity_score >= 3 or len(found_symptoms) >= 3:
            risk_level = 'high'
        elif severity_score >= 2 or len(found_symptoms) >= 2:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        # Generar evaluación personalizada
        assessment = self.risk_factors[risk_level]['message']
        
        # Recomendaciones específicas basadas en síntomas
        recommendations = []
        possible_conditions = []
        
        if 'dolor' in found_symptoms:
            recommendations.append("• Evita automedicarte con antibióticos")
            recommendations.append("• Mantén buena higiene íntima")
            possible_conditions.extend(["Clamidia", "Gonorrea", "ITU"])
        
        if 'secrecion' in found_symptoms:
            recommendations.append("• Observa color, olor y consistencia")
            recommendations.append("• Evita duchas vaginales")
            possible_conditions.extend(["Clamidia", "Gonorrea", "Tricomoniasis"])
        
        if 'lesiones' in found_symptoms:
            recommendations.append("• No toques las lesiones")
            recommendations.append("• Evita contacto sexual hasta diagnóstico")
            possible_conditions.extend(["Herpes genital", "Sífilis", "VPH"])
        
        if not recommendations:
            recommendations = ["• Consulta médica para evaluación completa", "• Mantén prácticas sexuales seguras"]
        
        if not possible_conditions:
            possible_conditions = ["Evaluación médica necesaria para diagnóstico"]
        
        return {
            'risk_level': risk_level,
            'assessment': assessment,
            'recommendations': '\n'.join(recommendations[:3]),  # Máximo 3 recomendaciones
            'possible_conditions': ', '.join(list(set(possible_conditions))[:3])  # Máximo 3 condiciones únicas
        }

    # ----------------- LOCALIZACIÓN DE CENTROS MÉDICOS -----------------
    async def handle_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        location = update.message.location
        user_id = update.effective_user.id
        
        # Simular búsqueda por coordenadas (en producción usarías una API real)
        latitude = location.latitude
        longitude = location.longitude
        
        # Para este ejemplo, asumimos Ciudad de México si está cerca
        if 19.3 <= latitude <= 19.5 and -99.2 <= longitude <= -99.0:
            city = "ciudad_mexico"
        else:
            city = "ciudad_mexico"  # Default
        
        await self.show_medical_centers_for_city(update, city, is_location=True)

    async def show_medical_centers_for_city(self, update, city_key: str, is_location: bool = False):
        if city_key not in self.medical_centers:
            text = """
🏥 **Centros Médicos**

No tengo información específica de centros médicos en tu área, pero puedes:

• Contactar centros de salud públicos locales
• Buscar clínicas privadas especializadas
• Consultar con tu médico de cabecera

📞 **Líneas de ayuda nacionales:**
• Emergencias: 911
• Tel-SIDA: 800-712-0886
            """
            keyboard = [[InlineKeyboardButton("⬅️ Volver", callback_data="menu")]]
        else:
            city_data = self.medical_centers[city_key]
            text = f"""
🏥 **Centros Médicos - {city_data['nombre']}**

Centros recomendados cerca de ti:
            """
            
            keyboard = []
            for i, center in enumerate(city_data['centros'][:3]):  # Máximo 3 centros
                text += f"""

**{center['nombre']}**
📍 {center['direccion']}
📞 {center['telefono']}
🕒 {center['horarios']}
🏥 Servicios: {', '.join(center['servicios'])}
                """
                keyboard.append([InlineKeyboardButton(f"📞 Llamar a {center['nombre']}", 
                                                    url=f"tel:{center['telefono']}")])
            
            keyboard.extend([
                [InlineKeyboardButton("🗺️ Ver más centros", callback_data=f"more_centers_{city_key}")],
                [InlineKeyboardButton("📅 Agendar cita", callback_data="book_appointment")],
                [InlineKeyboardButton("⬅️ Volver", callback_data="menu")]
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if is_location:
            await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            await update.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

    # ----------------- ENCICLOPEDIA INTERACTIVA -----------------
    async def show_encyclopedia(self, update):
        query = update.callback_query if hasattr(update, 'callback_query') else update
        
        text = """
📚 **Enciclopedia ETS Interactiva**

Explora información detallada sobre las infecciones de transmisión sexual más comunes:
        """
        
        keyboard = []
        for key, ets in self.ets_database.items():
            prevalence_emoji = "🔴" if ets['prevalencia'] == 'muy alta' else "🟡" if ets['prevalencia'] == 'alta' else "🟢"
            keyboard.append([InlineKeyboardButton(
                f"{prevalence_emoji} {ets['nombre']}", 
                callback_data=f"ets_detail_{key}"
            )])
        
        keyboard.extend([
            [InlineKeyboardButton("📊 Estadísticas generales", callback_data="general_stats")],
            [InlineKeyboardButton("🛡️ Guía de prevención", callback_data="prevention_guide")],
            [InlineKeyboardButton("⬅️ Volver", callback_data="menu")]
        ])
        
        await query.edit_message_text(text, parse_mode='Markdown', 
                                    reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_ets_detail(self, update, ets_key: str):
        query = update.callback_query
        ets = self.ets_database.get(ets_key)
        
        if not ets:
            await query.answer("Información no encontrada")
            return
        
        # Determinar síntomas según género del usuario si está disponible
        user_data = self.session_manager.get_user_data(query.from_user.id)
        gender = user_data.get('gender', '').lower()
        
        sintomas_text = f"**Síntomas comunes:**\n• {chr(10).join(ets['sintomas']['comunes'])}\n"
        
        if 'hombres' in ets['sintomas'] and 'masculino' in gender:
            sintomas_text += f"\n**Específicos en hombres:**\n• {chr(10).join(ets['sintomas']['hombres'])}\n"
        elif 'mujeres' in ets['sintomas'] and 'femenino' in gender:
            sintomas_text += f"\n**Específicos en mujeres:**\n• {chr(10).join(ets['sintomas']['mujeres'])}\n"
        
        text = f"""
📋 **{ets['nombre']}**
*Tipo: {ets['tipo'].title()} - Prevalencia: {ets['prevalencia'].title()}*

{sintomas_text}
**Información general:**
{ets['info']}

**Tratamiento:**
{ets['tratamiento']}

**Tiempo de aparición de síntomas:**
{ets['tiempo_sintomas']}

**Prevención:**
• {chr(10).join(ets['prevencion'])}

**Posibles complicaciones:**
• {chr(10).join(ets['complicaciones'])}

⚠️ **Nota importante:** {ets['sintomas']['asintomatico']}% de casos pueden ser asintomáticos.

💡 *Solo un profesional médico puede realizar un diagnóstico definitivo.*
        """
        
        keyboard = [
            [InlineKeyboardButton("🧪 Pruebas recomendadas", callback_data=f"tests_{ets_key}")],
            [InlineKeyboardButton("🏥 Encontrar centros", callback_data="find_centers")],
            [InlineKeyboardButton("📚 Volver a enciclopedia", callback_data="encyclopedia")],
            [InlineKeyboardButton("🏠 Menú principal", callback_data="menu")]
        ]
        
        await query.edit_message_text(text, parse_mode='Markdown', 
                                    reply_markup=InlineKeyboardMarkup(keyboard))

    # ----------------- GUÍA DE PRUEBAS MÉDICAS -----------------
    async def show_test_guide(self, update):
        query = update.callback_query
        user_data = self.session_manager.get_user_data(query.from_user.id)
        age = user_data.get('age', 0)
        
        text = f"""
🧪 **Guía Completa de Pruebas de ETS**

**Pruebas recomendadas según tu perfil:**
{self.get_recommended_tests(user_data)}

**Tipos de pruebas disponibles:**

🩸 **Análisis de sangre:**
• VIH, Sífilis, Hepatitis B/C
• Tiempo: 3-12 semanas post-exposición
• Ayuno: No necesario

🧪 **Análisis de orina:**
• Clamidia, Gonorrea
• Tiempo: 1-2 semanas post-exposición
• Primera orina del día

🔬 **Hisopado genital:**
• Herpes, VPH, Clamidia, Gonorrea
• Tiempo: Inmediato si hay síntomas
• Más preciso para diagnóstico

**Frecuencia recomendada:**
• Personas sexualmente activas: Anual
• Alto riesgo: Cada 3-6 meses
• Nueva pareja: Antes del contacto sin protección

**Preparación para las pruebas:**
• No orinar 2 horas antes (orina)
• No duchas vaginales 24h antes
• Informar medicamentos actuales
        """
        
        keyboard = [
            [InlineKeyboardButton("🏥 Dónde hacerse pruebas", callback_data="find_centers")],
            [InlineKeyboardButton("💰 Costos aproximados", callback_data="test_costs")],
            [InlineKeyboardButton("📅 Agendar cita", callback_data="book_appointment")],
            [InlineKeyboardButton("⬅️ Volver", callback_data="menu")]
        ]
        
        await query.edit_message_text(text, parse_mode='Markdown', 
                                    reply_markup=InlineKeyboardMarkup(keyboard))

    def get_recommended_tests(self, user_data: Dict) -> str:
        age = user_data.get('age', 0)
        gender = user_data.get('gender', '').lower()
        risk_level = user_data.get('risk_level', 'unknown')
        
        tests = []
        
        # Pruebas básicas para todos
        tests.append("• Panel básico de ETS (Clamidia, Gonorrea, Sífilis, VIH)")
        
        if age and age <= 26:
            tests.append("• Considerrar vacuna VPH si no la has recibido")
        
        if 'femenino' in gender:
            tests.append("• Papanicolaou (detección VPH)")
            tests.append("• Cultivo vaginal si hay síntomas")
        
        if risk_level == 'high':
            tests.append("• Panel completo incluyendo Hepatitis B/C")
            tests.append("• Repetir en 3 meses")
        
        return "\n".join(tests) if tests else "• Consulta con médico para recomendación personalizada"

    # ----------------- SISTEMA DE CITAS -----------------
    async def start_appointment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        text = """
📅 **Agendar Cita Médica**

Te ayudo a preparar tu cita médica. ¿Qué tipo de consulta necesitas?
        """
        
        keyboard = [
            [InlineKeyboardButton("🔍 Evaluación de síntomas", callback_data="appt_symptoms")],
            [InlineKeyboardButton("🧪 Pruebas de ETS", callback_data="appt_tests")],
            [InlineKeyboardButton("💊 Seguimiento de tratamiento", callback_data="appt_followup")],
            [InlineKeyboardButton("🛡️ Consulta preventiva", callback_data="appt_prevention")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="menu")]
        ]
        
        await query.edit_message_text(text, parse_mode='Markdown', 
                                    reply_markup=InlineKeyboardMarkup(keyboard))
        return APPOINTMENT_BOOKING

    async def handle_appointment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.callback_query:
            query = update.callback_query
            appointment_type = {
                'appt_symptoms': 'Evaluación de síntomas',
                'appt_tests': 'Pruebas de ETS',
                'appt_followup': 'Seguimiento de tratamiento',
                'appt_prevention': 'Consulta preventiva'
            }.get(query.data, 'Consulta general')
            
            text = f"""
📋 **Preparación para tu cita: {appointment_type}**

**Información que debes preparar:**
• Lista de síntomas y cuándo comenzaron
• Historial sexual reciente
• Medicamentos que tomas actualmente
• Preguntas que quieres hacer al médico

**Documentos a llevar:**
• Identificación oficial
• Credencial de seguro médico (si aplica)
• Resultados de pruebas previas

**Lista de centros médicos cercanos:**
            """
            
            keyboard = [
                [InlineKeyboardButton("🏥 Ver centros médicos", callback_data="find_centers")],
                [InlineKeyboardButton("📋 Lista de preparación", callback_data="appointment_checklist")],
                [InlineKeyboardButton("💬 Preguntas frecuentes", callback_data="appointment_faq")],
                [InlineKeyboardButton("✅ Listo, buscar centros", callback_data="find_centers")]
            ]
            
            await query.edit_message_text(text, parse_mode='Markdown', 
                                        reply_markup=InlineKeyboardMarkup(keyboard))
        
        return ConversationHandler.END

    # ----------------- CHAT LIBRE INTELIGENTE -----------------
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.lower()
        user_data = self.session_manager.get_user_data(user_id)
        
        # Actualizar interacciones
        self.session_manager.update_session(user_id, {'last_message': text})
        
        # Análisis avanzado del texto con respuestas contextuales
        response = self.generate_intelligent_response(text, user_data)
        
        await update.message.reply_text(
            response, 
            parse_mode='Markdown', 
            reply_markup=self.get_main_menu(user_id)
        )

    def generate_intelligent_response(self, text: str, user_data: Dict) -> str:
        """Genera respuestas inteligentes basadas en contexto y historial"""
        
        # Respuestas contextuales por categorías
        responses = {
            'dolor_sintomas': {
                'keywords': ['dolor', 'duele', 'molestia', 'ardor', 'quema'],
                'response': """
⚠️ **Síntomas de Dolor**

El dolor en la zona genital puede indicar:
• **Infecciones bacterianas** (Clamidia, Gonorrea)
• **Infecciones del tracto urinario**
• **Irritación por productos químicos**

**Recomendaciones inmediatas:**
• Evita jabones perfumados en la zona íntima
• Usa ropa interior de algodón
• Mantén buena hidratación
• {personalized_advice}

🏥 **Busca atención médica si:**
• El dolor empeora o persiste >48 horas
• Hay fiebre asociada
• Dificultad para orinar
                """
            },
            'secrecion_flujo': {
                'keywords': ['secreción', 'flujo', 'líquido', 'descarga', 'supura'],
                'response': """
🔍 **Secreción Genital Anormal**

**Características a observar:**
• **Color:** Normal (claro/blanco) vs. Anormal (amarillo/verde/gris)
• **Olor:** Sin olor fuerte vs. Olor desagradable
• **Consistencia:** Textura y cantidad

**Posibles causas:**
• **Bacterianas:** Clamidia, Gonorrea
• **Por hongos:** Candidiasis
• **Parasitarias:** Tricomoniasis

**No hagas:**
• Duchas vaginales
• Automedicación con antibióticos
• Ignorar cambios persistentes

{personalized_advice}
                """
            },
            'lesiones_heridas': {
                'keywords': ['ampolla', 'llaga', 'herida', 'úlcera', 'roncha', 'verruga'],
                'response': """
🚨 **Lesiones Genitales - Atención Prioritaria**

**Tipos de lesiones y posibles causas:**
• **Ampollas dolorosas:** Herpes genital
• **Úlceras indoloras:** Sífilis primaria  
• **Verrugas:** VPH (Virus del Papiloma Humano)
• **Lesiones irregulares:** Requieren evaluación urgente

**⚠️ IMPORTANTE:**
• No toques ni revientes las lesiones
• Evita contacto sexual hasta diagnóstico
• Lávate las manos después del contacto

**Busca atención médica URGENTE - estas lesiones requieren evaluación profesional inmediata.**

{personalized_advice}
                """
            },
            'prevencion': {
                'keywords': ['prevenir', 'evitar', 'proteger', 'cuidar', 'seguro'],
                'response': """
🛡️ **Prevención Efectiva de ETS**

**Métodos más efectivos:**
1. **Preservativos** - 98% efectividad si se usan correctamente
2. **Comunicación** - Hablar abiertamente con parejas
3. **Pruebas regulares** - Detectar infecciones asintomáticas
4. **Vacunación** - VPH y Hepatitis B disponibles

**Estrategias personalizadas para ti:**
{personalized_advice}

**¿Sabías que?** Muchas ETS son asintomáticas, por eso las pruebas regulares son clave.
                """
            },
            'pruebas_tests': {
                'keywords': ['prueba', 'test', 'examen', 'análisis', 'laboratorio'],
                'response': """
🧪 **Guía de Pruebas de ETS**

**Recomendaciones según tu perfil:**
{personalized_advice}

**Tipos de pruebas principales:**
• **Sangre:** VIH, Sífilis, Hepatitis (3-12 semanas post-exposición)
• **Orina:** Clamidia, Gonorrea (1-2 semanas post-exposición)
• **Hisopado:** Herpes, VPH (inmediato si hay síntomas)

**Ventana de detección:** Tiempo necesario para que una prueba sea confiable después de la exposición.

💡 **Tip:** Las pruebas son más precisas después del período de ventana.
                """
            }
        }
        
        # Buscar categoría más relevante
        for category, data in responses.items():
            if any(keyword in text for keyword in data['keywords']):
                # Personalizar respuesta
                personalized = self.get_personalized_advice(category, user_data)
                response = data['response'].format(personalized_advice=personalized)
                return response
        
        # Respuestas generales inteligentes
        if any(word in text for word in ['hola', 'buenos', 'buenas']):
            return f"""
¡Hola! 👋 

Soy tu asistente de salud sexual. Puedo ayudarte con:
• Evaluación de síntomas
• Información sobre ETS
• Guía de pruebas médicas
• Localización de centros médicos

**{self.get_personalized_greeting(user_data)}**

¿En qué puedo ayudarte hoy?
            """
        
        elif any(word in text for word in ['gracias', 'thank']):
            return """
¡De nada! 😊

Recuerda que tu salud sexual es importante. Si tienes más dudas o necesitas orientación, estoy aquí para ayudarte.

🔒 Todo es completamente confidencial.
            """
        
        # Respuesta por defecto más inteligente
        return f"""
💬 **Consulta de Salud Sexual**

Entiendo que tienes dudas sobre salud sexual. 

**Puedo ayudarte específicamente con:**
• Análisis de síntomas que describas
• Información sobre prevención
• Orientación sobre pruebas médicas
• Localización de centros de atención

{self.get_personalized_advice('general', user_data)}

💡 **Tip:** Sé específico/a con tus síntomas o preguntas para darte mejor orientación.
        """

    def get_personalized_advice(self, category: str, user_data: Dict) -> str:
        """Genera consejos personalizados basados en el perfil del usuario"""
        
        age = user_data.get('age', 0)
        gender = user_data.get('gender', '').lower()
        risk_level = user_data.get('risk_level', 'unknown')
        
        advice = []
        
        if category == 'dolor_sintomas':
            if risk_level == 'high':
                advice.append("Dado tu nivel de riesgo, considera hacerte pruebas completas")
            if age and age < 25:
                advice.append("A tu edad, Clamidia y Gonorrea son más comunes")
        
        elif category == 'prevencion':
            if age and age <= 26:
                advice.append("La vacuna VPH es especialmente recomendada a tu edad")
            if risk_level != 'low':
                advice.append("Considera pruebas cada 3-6 meses dada tu situación")
        
        elif category == 'pruebas_tests':
            if 'femenino' in gender:
                advice.append("Incluye Papanicolaou para detección de VPH")
            if age and age < 25:
                advice.append("Enfócate en pruebas de Clamidia y Gonorrea")
        
        return " • ".join(advice) if advice else "Consulta médica para recomendación personalizada"

    def get_personalized_greeting(self, user_data: Dict) -> str:
        """Genera saludos personalizados"""
        
        age = user_data.get('age')
        if age:
            if age < 25:
                return "Veo que eres joven, la prevención es clave a tu edad"
            elif age >= 25:
                return "La salud sexual es importante a cualquier edad"
        
        return "Tu salud sexual es mi prioridad"

    # ----------------- CALLBACKS Y NAVEGACIÓN -----------------
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        callback_handlers = {
            "menu": self.show_main_menu_callback,
            "encyclopedia": self.show_encyclopedia,
            "test_guide": self.show_test_guide,
            "find_centers": self.show_location_options,
            "emergency": self.show_emergency_info,
            "quick_symptoms": self.show_quick_symptoms,
            "free_chat": self.show_free_chat_info,
            "profile": self.show_profile_callback,
            "setup_profile": self.setup_profile_callback,
            "skip_setup": self.skip_setup_callback
        }
        
        # Manejar callbacks específicos
        if query.data.startswith("ets_detail_"):
            ets_key = query.data.replace("ets_detail_", "")
            await self.show_ets_detail(query, ets_key)
        elif query.data.startswith("rating_"):
            await self.handle_feedback_rating(query)
        elif query.data.startswith("city_"):
            city = query.data.replace("city_", "")
            await self.show_medical_centers_for_city(query, city)
        elif query.data in callback_handlers:
            await callback_handlers[query.data](query)
        else:
            await query.edit_message_text(
                "⚠️ Opción no reconocida. Volviendo al menú principal.",
                reply_markup=self.get_main_menu(query.from_user.id)
            )

    async def show_main_menu_callback(self, query):
        text = "🏥 **Menú Principal**\n\n¿En qué puedo ayudarte hoy?"
        await query.edit_message_text(
            text, 
            parse_mode='Markdown', 
            reply_markup=self.get_main_menu(query.from_user.id)
        )

    async def show_location_options(self, query):
        text = """
📍 **Encontrar Centros Médicos**

Selecciona tu ubicación para encontrar centros especializados cerca de ti:
        """
        
        keyboard = [
            [InlineKeyboardButton("📍 Compartir ubicación", callback_data="share_location")],
            [InlineKeyboardButton("🏙️ Ciudad de México", callback_data="city_ciudad_mexico")],
            [InlineKeyboardButton("🌆 Guadalajara", callback_data="city_guadalajara")],
            [InlineKeyboardButton("🏘️ Monterrey", callback_data="city_monterrey")],
            [InlineKeyboardButton("🏖️ Otras ciudades", callback_data="other_cities")],
            [InlineKeyboardButton("⬅️ Volver", callback_data="menu")]
        ]
        
        await query.edit_message_text(text, parse_mode='Markdown', 
                                    reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_emergency_info(self, query):
        text = """
🆘 **INFORMACIÓN DE EMERGENCIA**

**¿Cuándo buscar atención inmediata?**
• Dolor severo que no mejora
• Fiebre alta (>38.5°C) con síntomas genitales
• Sangrado abundante anormal
• Lesiones genitales que crecen rápidamente
• Dificultad severa para orinar

**Números de emergencia México:**
• **911** - Emergencias médicas
• **065** - Cruz Roja Mexicana
• **Locatel:** 56-58-1111 (CDMX)
• **Tel-SIDA:** 800-712-0886

**Centros de atención 24/7:**
• Hospitales públicos de tu localidad
• Clínicas privadas con urgencias
• Centros de salud con guardia nocturna

⚠️ **No esperes** si presentas síntomas graves.
        """
        
        keyboard = [
            [InlineKeyboardButton("🏥 Centros médicos", callback_data="find_centers")],
            [InlineKeyboardButton("📞 Más números útiles", callback_data="more_emergency_numbers")],
            [InlineKeyboardButton("⬅️ Volver", callback_data="menu")]
        ]
        
        await query.edit_message_text(text, parse_mode='Markdown', 
                                    reply_markup=InlineKeyboardMarkup(keyboard))

    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "❌ **Conversación cancelada**\n\nVolviendo al menú principal.",
            parse_mode='Markdown',
            reply_markup=self.get_main_menu(update.effective_user.id)
        )
        return ConversationHandler.END

    async def handle_feedback_rating(self, query):
        rating = int(query.data.replace("rating_", ""))
        user_id = query.from_user.id
        
        # Guardar rating (en producción usarías una base de datos)
        user_data = self.session_manager.get_user_data(user_id)
        user_data['last_rating'] = rating
        
        thank_you_messages = {
            5: "¡Excelente! 🌟 Me alegra haber sido de gran ayuda.",
            4: "¡Muy bien! 😊 Gracias por tu feedback positivo.",
            3: "¡Bien! 👍 Seguiré mejorando para ayudarte mejor.",
            2: "Gracias por tu honestidad. 💭 ¿Hay algo específico que pueda mejorar?",
            1: "Lamento no haber cumplido tus expectativas. 😔 Tu feedback me ayuda a mejorar."
        }
        
        await query.edit_message_text(
            f"⭐ **Rating: {rating}/5**\n\n{thank_you_messages[rating]}",
            parse_mode='Markdown'
        )

    # ----------------- EJECUCIÓN Y CONFIGURACIÓN -----------------
    def run_webhook(self):
        """Ejecuta el bot usando webhook para Render"""
        port = int(os.environ.get("PORT", 5000))
        
        # Configurar webhook
        self.application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=self.token,
            webhook_url=f"{WEBHOOK_URL}/{self.token}",
            drop_pending_updates=True
        )
        
        logger.info(f"Bot iniciado en puerto {port} con webhook {WEBHOOK_URL}")

def main():
    """Función principal"""
    if not TOKEN or not WEBHOOK_URL:
        logger.error("Faltan variables de entorno requeridas")
        return
    
    try:
        bot = ETSBotAdvanced(TOKEN)
        logger.info("Bot iniciado correctamente")
        bot.run_webhook()
    except Exception as e:
        logger.error(f"Error al iniciar el bot: {e}")

if __name__ == "__main__":
    main()