import streamlit as st

if ('email' not in st.session_state or 'password' not in st.session_state): st.header('Login First!')
elif (st.session_state.email == '' or st.session_state.password == ''): st.header('Login First!')
else:
    # TODO
    st.header('In Progress')