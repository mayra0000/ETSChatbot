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
**{i+1}. {center['nombre']}**
• Dirección: {center['direccion']}
• Teléfono: {center['telefono']}
• Servicios: {', '.join(center['servicios'])}
• Horarios: {center['horarios']}
"""
            keyboard.append([InlineKeyboardButton("⬅️ Volver", callback_data="menu")])
        
        if is_location:
            await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            query = update.callback_query
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))

    # ----------------- Funciones faltantes -----------------

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = query.from_user.id
        user_data = self.session_manager.get_user_data(user_id)

        if query.data == "setup_profile":
            await query.edit_message_text("✏️ **Configuración de perfil**\n\n¿Cuál es tu edad?", parse_mode='Markdown')
            return ASKING_AGE
        
        if query.data == "skip_setup" or query.data == "menu":
            text = "🏠 **Menú Principal**\n\n¿En qué puedo ayudarte hoy?"
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=self.get_main_menu(user_id))
            return ConversationHandler.END
        
        if query.data == "quick_symptoms":
            text = "🔍 **Síntomas Rápidos**\n\nDescribe en una frase tus síntomas principales. Por ejemplo: 'dolor al orinar y secreción'."
            await query.edit_message_text(text, parse_mode='Markdown')
            return SYMPTOM_DETAIL

        if query.data == "encyclopedia":
            text = "📚 **Enciclopedia de ETS**\n\nSelecciona una enfermedad para ver su información detallada:"
            ets_keyboard = [[InlineKeyboardButton(f"📋 {ets['nombre']}", callback_data=f"info_{key}")] for key, ets in self.ets_database.items()]
            ets_keyboard.append([InlineKeyboardButton("⬅️ Volver", callback_data="menu")])
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(ets_keyboard))
            
        if query.data.startswith("info_"):
            ets_key = query.data.replace("info_", "")
            ets = self.ets_database.get(ets_key)
            if ets:
                text = f"""
📋 **{ets['nombre']}**

**Tipo:** {ets['tipo'].capitalize()}
**Prevalencia:** {ets['prevalencia'].capitalize()}

**Síntomas:**
{', '.join(ets['sintomas']['comunes'])}

**Información general:**
{ets['info']}

**Tratamiento:**
{ets['tratamiento']}

**Prevención:**
{', '.join(ets['prevencion'])}

**Tiempo de aparición de síntomas:** {ets['tiempo_sintomas']}

**Complicaciones:** {', '.join(ets['complicaciones'])}
                """
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📚 Volver a Enciclopedia", callback_data="encyclopedia")],
                    [InlineKeyboardButton("🏠 Menú Principal", callback_data="menu")]
                ])
                await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)
            else:
                await query.edit_message_text("Información no encontrada.")

        if query.data == "test_guide":
            text = """
🧪 **Guía de Pruebas de ETS**

**¿Cuándo hacerme una prueba?**
• Si has tenido relaciones sexuales sin protección.
• Antes de iniciar una nueva relación sexual.
• Si tu pareja sexual te informa de una ETS.
• Al presentar síntomas.
• Anualmente si eres sexualmente activo.

**¿Qué esperar?**
Las pruebas pueden ser de sangre, orina o hisopado, dependiendo de la ETS. Son procedimientos rápidos y confidenciales.

**Recuerda:** Los Centros de Salud Públicos suelen ofrecer pruebas gratuitas.
"""
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Volver", callback_data="menu")]])
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard)

        if query.data == "find_centers":
            text = """
🏥 **Encontrar Centros Médicos**

Para encontrar los centros más cercanos, por favor, **comparte tu ubicación** o selecciona una ciudad de la lista.
"""
            await query.edit_message_text(text, parse_mode='Markdown', reply_markup=self.get_location_keyboard())

        if query.data == "emergency":
            await self.emergency(update, context)

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.lower()
        
        # Lógica para manejar texto de ciudades
        city_map = {
            'ciudad de méxico': 'ciudad_mexico',
            'guadalajara': 'guadalajara',
            'monterrey': 'monterrey',
            'cancún': 'cancun'
        }
        
        if text in city_map:
            await self.show_medical_centers_for_city(update, city_map[text], is_location=True)
            return

        # Si el flujo de conversación no está activo, redirigir al menú principal
        if context.user_data.get('state', None) is None:
            await update.message.reply_text(
                "Por favor, usa los botones del menú para interactuar conmigo.",
                reply_markup=self.get_main_menu(user_id)
            )
        # La lógica de ConversationHandler se encargará de las respuestas dentro de un estado

    async def handle_risk_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Esta función podría manejar interacciones con botones dentro de la evaluación de riesgo
        query = update.callback_query
        await query.answer()
        # Por ahora, solo termina la conversación
        await query.edit_message_text("¡Gracias por completar la evaluación!", parse_mode='Markdown')
        return ConversationHandler.END

    async def start_appointment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        text = """
📅 **Agendar una cita**

Este servicio es solo una simulación. Escribe la fecha y hora preferida para tu cita y el bot te dará una confirmación de prueba.

Ejemplo: `Mañana a las 10:00 AM`
"""
        await query.edit_message_text(text, parse_mode='Markdown')
        return APPOINTMENT_BOOKING

    async def handle_appointment(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        appointment_text = update.message.text
        confirmation_text = f"""
✅ **¡Cita Agendada!**

Hemos recibido tu solicitud para una cita para el:
**{appointment_text}**

Un profesional médico se pondrá en contacto contigo a través de este chat para confirmar los detalles.
"""
        await update.message.reply_text(confirmation_text, parse_mode='Markdown')
        return ConversationHandler.END

    async def handle_feedback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        rating = int(query.data.replace("rating_", ""))
        
        # Aquí podrías guardar el rating en una base de datos para análisis
        user_id = query.from_user.id
        logger.info(f"Feedback recibido de {user_id}: {rating} estrellas.")
        
        await query.edit_message_text(
            f"🌟 **¡Gracias por tu valoración de {rating} estrellas!** Tu feedback nos ayuda a mejorar. 😊",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "❌ **Conversación cancelada.**\n\n¿En qué más puedo ayudarte?",
            reply_markup=self.get_main_menu(update.effective_user.id)
        )
        return ConversationHandler.END

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = """
ℹ️ **Ayuda - Asistente de Salud Sexual**

**Comandos:**
• /start - Iniciar
• /perfil - Ver mi perfil
• /ayuda - Esta ayuda
• /emergencia - Info de emergencia

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
        if update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text(text, parse_mode='Markdown')

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Esta es solo una función de ejemplo
        await update.message.reply_text("📊 **Estadísticas de uso**\n\n(Pronto tendrás acceso a tus estadísticas de salud personal)")

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