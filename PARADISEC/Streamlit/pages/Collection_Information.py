import math
import pandas as pd
import streamlit as st
import time

if (st.session_state.get('use_dev', False)): st.switch_page('pages/Collection_Information_dev.py')

if (st.session_state.logged_in == False): st.header('Login First!')
else:
    # Gets desired collection from user
    st.header('Query A Collection')
    st.selectbox('Collection ID:', st.session_state.collection_identifiers_list, None, key = 'collection', placeholder = 'Select Collection Identifier', persist_state = 'session')

    if (st.session_state.collection != None):
        # Retrieves basic collection information
        query = '''
            query($identifier: ID!) {
                collection(identifier: $identifier) {
                    title
                    description
                }
            }
        '''
        variables = {'identifier': st.session_state.collection}
        response = st.session_state.session.post(
            st.session_state.API_URL,
            json = {'query': query, 'variables': variables}
        )

        st.subheader('Collection Title')
        st.write(response.json()['data']['collection']['title'])
        st.subheader('Collection Description')
        st.write(response.json()['data']['collection']['description'])



        # Retrieves all items within that collection
        query = '''
            query($full_identifier: String!) {
                items(full_identifier: $full_identifier) {
                    total
                }
            }
        '''
        variables = {'full_identifier': st.session_state.collection}
        response = st.session_state.session.post(
            st.session_state.API_URL,
            json = {'query': query, 'variables': variables}
        )

        total_items = response.json()['data']['items']['total']
        pages = math.ceil(total_items / st.session_state.PAGE_LIMIT)

        collection_items = []
        for page in range(pages):
            query = '''
                query($limit: Int!, $page: Int!, $full_identifier: String!) {
                    items(limit: $limit, page: $page, full_identifier: $full_identifier) {
                        results {
                            full_identifier
                            title
                            description
                        }
                    }
                }
            '''
            variables = {'limit': st.session_state.PAGE_LIMIT, 'page': (page + 1), 'full_identifier': st.session_state.collection}
            response = st.session_state.session.post(
                st.session_state.API_URL,
                json = {'query': query, 'variables': variables}
            )
            collection_items.extend(response.json()['data']['items']['results'])
            time.sleep(0.2)

        st.subheader('Items in Collection')
        st.dataframe(pd.DataFrame(collection_items))



    # Retrieves specific item information
    st.subheader('Specific Item Information')
    st.selectbox('Item Full Identifier:', st.session_state.item_identifiers_list, None, key = 'item', placeholder = 'Select Item Full Identifier', persist_state = 'session')

    if (st.session_state.item != None):
        query = '''
            query($fullIdentifier: ID!) {
                item(fullIdentifier: $fullIdentifier) {
                    access_class
                    access_condition_name
                    access_narrative
                    born_digital
                    boundaries {
                        east_limit
                        north_limit
                        south_limit
                        west_limit
                    }
                    citation
                    collection {
                        title
                    }
                    collector {
                        name
                    }
                    content_languages {
                        name
                    }
                    countries {
                        name
                    }
                    created_at
                    data_categories {
                        name
                    }
                    data_types {
                        name
                    }
                    description
                    dialect
                    digitised_on
                    discourse_type {
                        name
                    }
                    doi
                    essences {
                        filename
                        permalink
                    }
                    essences_count
                    full_identifier
                    id
                    identifier
                    ingest_notes
                    item_agents {
                        role_name
                        user_name
                    }
                    language
                    metadata_exportable
                    operator {
                        name
                    }
                    original_media
                    originated_on
                    originated_on_narrative
                    permalink
                    private
                    public
                    received_on
                    region
                    subject_languages {
                        name
                    }
                    title
                    tracking
                    university {
                        name
                    }
                    updated_at
                }
            }
        '''
        variables = {'fullIdentifier': st.session_state.item}
        response = st.session_state.session.post(
            st.session_state.API_URL,
            json = {'query': query, 'variables': variables}
        )
        st.write('All available item information (sub object information simplified):')
        st.dataframe(pd.DataFrame(response.json()['data']))