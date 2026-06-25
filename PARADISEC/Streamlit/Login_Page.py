import streamlit as st
import requests
from bs4 import BeautifulSoup
import json

st.session_state.enforced_page_limit = 500

# Sets up session and login process
st.session_state.session = requests.Session()

login_page = st.session_state.session.get('https://admin-catalog.paradisec.org.au/users/sign_in')
soup = BeautifulSoup(login_page.text, 'html.parser')
csrf = soup.find('input', {'name': 'authenticity_token'})['value']

# Gets login information from user
st.header('Log Into PARADISEC')
if ('email' not in st.session_state): st.session_state.email = st.text_input('Email:')
else: st.session_state.email = st.text_input(label='Email:', value=st.session_state.email)
if ('password' not in st.session_state): st.session_state.password = st.text_input(label='Password:', type='password')
else: st.session_state.password = st.text_input(label='Password:', type='password', value=st.session_state.password)



if (st.session_state.email != '' and st.session_state.password != ''):
    # Logs in user and gets authentication for GraphQL
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

    st.subheader('Logged in successfully!')