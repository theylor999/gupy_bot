import pandas as pd
import requests
from urllib.parse import quote
from difflib import get_close_matches
from datetime import datetime, timedelta, timezone
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

df_cidades = pd.read_csv('cidades.csv')
df_estados = pd.read_csv('estados.csv')
TELEGRAM_BOT_TOKEN = "7600076583:AAFZ4q5vy65rK6KimQ2LFleK6u7VXYvBCOI"
HOURS, STATE, CITIES, SEARCH = range(4)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bem vindo ao bot de vagas! Você quer receber vagas de quantas horas atrás?")
    return HOURS

async def get_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data['hours'] = int(update.message.text)
        await update.message.reply_text("Digite um estado (ou 'pular' para ignorar):")
        return STATE
    except ValueError:
        await update.message.reply_text("Por favor, digite um número válido.")
        return HOURS

async def get_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.lower() == 'pular':
        context.user_data['state'] = ""
        context.user_data['cities'] = ""
        await update.message.reply_text("Digite as vagas para pesquisar:")
        return SEARCH
    
    matches = get_close_matches(text, df_estados['estado'].tolist(), n=1, cutoff=0.6)
    if matches:
        estado_encontrado = matches[0]
        context.user_data['state'] = df_estados[df_estados['estado'] == estado_encontrado]['estado_formatado'].iloc[0]
        await update.message.reply_text("Digite as cidades separadas por vírgula (ou 'pular' para ignorar):")
        return CITIES
    else:
        await update.message.reply_text("Estado não encontrado. Tente novamente:")
        return STATE

async def get_cities(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.lower() == 'pular':
        context.user_data['cities'] = ""
    else:
        cidades_input = text.split(',')
        cidades_formatadas = []
        for cidade in cidades_input:
            cidade = cidade.strip()
            matches = get_close_matches(cidade, df_cidades['cidade'].tolist(), n=1, cutoff=0.6)
            if matches:
                cidade_encontrada = matches[0]
                cidade_formatada = df_cidades[df_cidades['cidade'] == cidade_encontrada]['cidade_formatada'].iloc[0]
                cidades_formatadas.append(cidade_formatada)
        context.user_data['cities'] = ','.join(cidades_formatadas)

    await update.message.reply_text("Digite as vagas para pesquisar:")
    return SEARCH

def traduzir_modelo(modelo):
    traducoes = {"on-site": "Presencial", "hybrid": "Híbrido", "remote": "Remoto"}
    return traducoes.get(modelo.lower(), modelo)

async def search_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pesquisa = quote(update.message.text)
    state = context.user_data.get('state', '')
    cities = context.user_data.get('cities', '')
    
    if state:
        if cities:
            response = requests.get(
                f'https://portal.api.gupy.io/api/v1/jobs?city={cities}&jobName={pesquisa}&state={state}')
        else:
            response = requests.get(
                f'https://portal.api.gupy.io/api/v1/jobs?jobName={pesquisa}&state={state}')
    else:
        response = requests.get(
            f'https://portal.api.gupy.io/api/v1/jobs?jobName={pesquisa}')

    vagas = response.json()['data']
    agora = datetime.now(timezone.utc)
    tempo = agora - timedelta(hours=context.user_data['hours'])

    await update.message.reply_text("Buscando vagas...")

    for vaga in vagas:
        nome = vaga.get('name')
        page = vaga.get('careerPageName')
        cidade = vaga.get('city')
        link = vaga.get('jobUrl')
        modelo = traduzir_modelo(vaga.get('workplaceType', 'Desconhecido'))
        data_publicacao = vaga.get('publishedDate')
        data_vaga = datetime.strptime(data_publicacao, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        data_formatada = data_vaga.strftime('%d/%m/%Y às %H:%M')

        if cidade == 'Porto Alegre' and modelo not in ['Híbrido', 'Remoto']:
            continue

        if data_vaga >= tempo:
            mensagem = f'*{nome}* - {page}\n📍 {cidade}\n🏢 {modelo}\n🗓 Publicada em {data_formatada}\n🔗 [Acesse a vaga]({link})'
            await update.message.reply_text(mensagem, parse_mode='Markdown')

    await update.message.reply_text("Busca finalizada! Use /start para fazer uma nova busca.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operação cancelada. Use /start para começar novamente.")
    return ConversationHandler.END

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_hours)],
            STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_state)],
            CITIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_cities)],
            SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_jobs)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()