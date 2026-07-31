import streamlit as st
import requests
from bs4 import BeautifulSoup
import base64
import os
import hashlib
from urllib.parse import urlparse, parse_qs

# Setting up constants needed across pages and functions large enough to avoid re-running
st.session_state.API_URL = 'https://admin-catalog.paradisec.org.au/graphql'
st.session_state.PAGE_LIMIT = 500

@st.cache_data
def read_files():
    lists = {}
    with open('collection_identifiers.txt', 'r') as file: lists['collection_identifiers_list'] = file.read().splitlines()
    with open('collectors.txt', 'r') as file: lists['collectors_list'] = file.read().splitlines()
    with open('item_identifiers.txt', 'r') as file: lists['item_identifiers_list'] = file.read().splitlines()
    with open('languages.txt', 'r') as file: lists['languages_list'] = file.read().splitlines()
    with open('regions.txt', 'r') as file: lists['regions_list'] = file.read().splitlines()
    with open('universities.txt', 'r') as file: lists['universities_list'] = file.read().splitlines()

    return lists

for key, value in read_files().items(): st.session_state[key] = value



# Logic to run new login
if ('logging_in' not in st.session_state): st.session_state.logging_in = False
if ('logged_in' not in st.session_state): st.session_state.logged_in = False

def login(): st.session_state.logging_in = True



# Gets login information from user
st.header('Log Into PARADISEC')

if ('email' not in st.session_state): st.session_state.email = st.text_input('Email:', on_change = login, icon = ':material/mail:')
else: st.session_state.email = st.text_input('Email:', st.session_state.email, on_change = login, icon = ':material/mail:')

if ('password' not in st.session_state): st.session_state.password = st.text_input('Password:', type = 'password', on_change = login, icon = ':material/key:')
else: st.session_state.password = st.text_input('Password:', st.session_state.password, type = 'password', on_change = login, icon = ':material/key:')



# Logs in user and gets authentication for GraphQL
if (st.session_state.logging_in):
    if (st.session_state.email != '' and st.session_state.password != ''):
        st.session_state.session = requests.Session()

        login_page = st.session_state.session.get('https://admin-catalog.paradisec.org.au/users/sign_in')
        soup = BeautifulSoup(login_page.text, 'html.parser')
        csrf = soup.find('input', {'name': 'authenticity_token'})['value']

        response = st.session_state.session.post(
            'https://admin-catalog.paradisec.org.au/users/sign_in',
            data = {
                'authenticity_token': csrf,
                'user[email]': st.session_state.email,
                'user[password]': st.session_state.password
            }
        )

        try:
            response.raise_for_status()
            st.session_state.logged_in = True
        except: st.session_state.logged_in = False



        # Gets authentication token to access raw files
        if (st.session_state.logged_in):
            # PKCE security to protect against authorization code interception attacks
            verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b'=').decode()
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()

            response = st.session_state.session.get(
                'https://admin-catalog.paradisec.org.au/oauth/authorize',
                params = {
                    'response_type': 'code',
                    'client_id': '8XJwJIeei7hyeikp5tT-qvhYmFbrGdqGJ0zzS4GqwIQ',
                    'redirect_uri': 'https://catalog.paradisec.org.au/auth/callback',
                    'scope': 'public openid',
                    'code_challenge': challenge,
                    'code_challenge_method': 'S256'
                },
                allow_redirects = False
            )
            location = response.headers.get('location')
            code = parse_qs(urlparse(location).query).get('code')[0]

            token_response = st.session_state.session.post(
                'https://admin-catalog.paradisec.org.au/oauth/token',
                data = {
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': 'https://catalog.paradisec.org.au/auth/callback',
                    'client_id': '8XJwJIeei7hyeikp5tT-qvhYmFbrGdqGJ0zzS4GqwIQ',
                    'code_verifier': verifier
                }
            )

            st.session_state.raw_file_auth_token = token_response.json()["access_token"]

    st.session_state.logging_in = False



# Displays success/failure of login attempt
if (st.session_state.logged_in): st.subheader('Login Successful!')
else: st.subheader('Login Failed...')