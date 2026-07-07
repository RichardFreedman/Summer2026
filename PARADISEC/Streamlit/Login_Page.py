import streamlit as st
import requests
from bs4 import BeautifulSoup
import json

# Setting up constants needed across pages and functions large enough to avoid re-running
st.session_state.enforced_page_limit = 500

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

def login(): st.session_state.logging_in = True



# Gets login information from user
st.header('Log Into PARADISEC')

if ('email' not in st.session_state): st.session_state.email = st.text_input('Email:', on_change=login, icon=':material/mail:')
else: st.session_state.email = st.text_input('Email:', st.session_state.email, on_change=login, icon=':material/mail:')

if ('password' not in st.session_state): st.session_state.password = st.text_input('Password:', type='password', on_change=login, icon=':material/key:')
else: st.session_state.password = st.text_input('Password:', st.session_state.password, type='password', on_change=login, icon=':material/key:')



# Logs in user and gets authentication for GraphQL
if (st.session_state.logging_in):
    if (st.session_state.email != '' and st.session_state.password != ''):
        st.session_state.session = requests.Session()

        login_page = st.session_state.session.get('https://admin-catalog.paradisec.org.au/users/sign_in')
        soup = BeautifulSoup(login_page.text, 'html.parser')
        csrf = soup.find('input', {'name': 'authenticity_token'})['value']

        st.session_state.session.post(
            'https://admin-catalog.paradisec.org.au/users/sign_in',
            data={
                'authenticity_token': csrf,
                'user[email]': st.session_state.email,
                'user[password]': st.session_state.password,
            }
        )

        graphiql_page = st.session_state.session.get('https://admin-catalog.paradisec.org.au/graphiql')
        soup = BeautifulSoup(graphiql_page.text, 'html.parser')
        container = soup.find(id='graphiql-container')
        headers_data = json.loads(container['data-headers'])

        st.session_state.csrf_token = headers_data['X-CSRF-Token']

        # TODO add check to see if login was actually successful?
        st.subheader('Log In Process Complete')

    st.session_state.logging_in = False