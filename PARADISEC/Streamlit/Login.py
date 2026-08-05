import base64
from bs4 import BeautifulSoup
import hashlib
import mimetypes
import os
import requests
import streamlit as st
from urllib.parse import urlparse, parse_qs

# Initial setup
st.session_state.API_URL = 'https://admin-catalog.paradisec.org.au/graphql'
st.session_state.PAGE_LIMIT = 500

mimetypes.add_type('application/eaf+xml', '.eaf')
mimetypes.add_type('application/flextext+xml', '.flextext')
mimetypes.add_type('application/x-subrip', '.srt')

@st.cache_data
def read_files() -> dict:
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



# Developer toggle: routes Collection Information / Text Search to their in-development versions
if ('use_dev' not in st.session_state): st.session_state.use_dev = False
with st.sidebar:
    st.session_state.use_dev = st.checkbox('Use Dev Pages', st.session_state.use_dev, help = 'When enabled, the Collection Information and Text Search pages open their in-development versions instead.')



# Gets login information from user
st.header('Log Into PARADISEC')

st.text_input('Email:', key = 'email', on_change = login, icon = ':material/mail:', persist_state = 'session')
st.text_input('Password:', key = 'password', type = 'password', on_change = login, icon = ':material/key:', persist_state = 'session')



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



        # Gets authentication token and sets up session to access raw files
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

            raw_file_auth_token = token_response.json()["access_token"]

            st.session_state.raw_session = requests.Session()
            st.session_state.raw_session.params.update({'disposition': 'inline'})
            st.session_state.raw_session.headers.update({'Authorization': f'Bearer {raw_file_auth_token}'})

    st.session_state.logging_in = False



# Displays success/failure of login attempt
if (st.session_state.logged_in): st.subheader('Login Successful!')
else: st.subheader('Login Failed...')