import streamlit as st
import pandas as pd

if ('email' not in st.session_state or 'password' not in st.session_state): st.header('Login First!')
elif (st.session_state.email == '' or st.session_state.password == ''): st.header('Login First!')
else:
    # Gets desired collection from user
    st.header('Query A Collection')
    if ('collection' not in st.session_state): st.session_state.collection = st.text_input('Collection ID:')
    else: st.session_state.collection = st.text_input(label='Collection ID:', value=st.session_state.collection)



    if (st.session_state.collection != ''):
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
            'https://admin-catalog.paradisec.org.au/graphql',
            json={'query': query, 'variables': variables},
            headers={
                'Content-Type': 'application/json',
                'X-CSRF-Token': st.session_state.csrf_token
            }
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
            'https://admin-catalog.paradisec.org.au/graphql',
            json={'query': query, 'variables': variables},
            headers={
                'Content-Type': 'application/json',
                'X-CSRF-Token': st.session_state.csrf_token
            }
        )

        total_items = response.json()['data']['items']['total']
        pages = total_items // st.session_state.enforced_page_limit
        if ((total_items % st.session_state.enforced_page_limit) != 0): pages = pages + 1

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
            variables = {'limit': st.session_state.enforced_page_limit, 'page': (page + 1), 'full_identifier': st.session_state.collection}
            response = st.session_state.session.post(
                'https://admin-catalog.paradisec.org.au/graphql',
                json={'query': query, 'variables': variables},
                headers={
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': st.session_state.csrf_token
                }
            )
            collection_items.extend(response.json()['data']['items']['results'])

        # col1, col2 = st.columns(2)

        # col1.subheader('Items in Collection')
        # col1.dataframe(pd.DataFrame(collection_items))
        st.subheader('Items in Collection')
        st.dataframe(pd.DataFrame(collection_items))
        # col1.json(collection_items)



        # Retrieves specific item information
        # col2.subheader('Specific Item Information')
        # if ('item' not in st.session_state): st.session_state.item = col2.text_input('Item Full Identifier:')
        # else: st.session_state.item = col2.text_input(label='Item Full Identifier:', value=st.session_state.item)
        st.subheader('Specific Item Information')
        if ('item' not in st.session_state): st.session_state.item = st.text_input('Item Full Identifier:')
        else: st.session_state.item = st.text_input(label='Item Full Identifier:', value=st.session_state.item)



        if (st.session_state.item != ''):
            # item = st.session_state.item.strip('"')

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
            # variables = {'fullIdentifier': item}
            variables = {'fullIdentifier': st.session_state.item}
            response = st.session_state.session.post(
                'https://admin-catalog.paradisec.org.au/graphql',
                json={'query': query, 'variables': variables},
                headers={
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': st.session_state.csrf_token
                }
            )

            # col2.write('All available item information (sub categories simplified):')
            # col2.dataframe(pd.DataFrame(response.json()['data']))
            st.write('All available item information (sub object information simplified):')
            st.dataframe(pd.DataFrame(response.json()['data']))
            # col2.write(response.json())