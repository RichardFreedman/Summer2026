import streamlit as st
import pandas as pd

if (not st.session_state.get('use_dev', False)): st.switch_page('pages/Collection_Information.py')

if (st.session_state.logged_in == False): st.header('Login First!')
else:
    st.header('Query Collections DEV')

    with st.expander('About This Page & How the Query Works'):
        st.markdown('''
            This page queries the PARADISEC catalog's GraphQL API for information about one or more collections and the items they contain.

            For each collection identifier selected below, the app sends a `collection` query (for the title and description) and one or more paginated `items` queries (using `full_identifier`) to retrieve every item belonging to that collection. The results from all selected collections are combined into a single report below.

            The **Specific Item Information** section is then limited to items found in the collection(s) you selected, so you can drill into the full metadata record for a single item.

            Turn on **Show Query** below to see the exact GraphQL query text and variables sent to the API for each request.
        ''')

    show_query = st.checkbox('Show Query', help = 'Display the GraphQL query text and variables sent to the API')

    # Gets desired collection(s) from user
    if ('collections' in st.session_state and st.session_state.collections): default_collections = st.session_state.collections
    else: default_collections = []
    st.session_state.collections = st.multiselect('Collection ID(s):', st.session_state.collection_identifiers_list, default = default_collections, placeholder = 'Select One or More Collection Identifiers')

    collection_items = []
    if (len(st.session_state.collections) > 0):
        queries_sent = []

        # Retrieves basic collection information for each selected collection
        collection_info_query = '''
            query($identifier: ID!) {
                collection(identifier: $identifier) {
                    title
                    description
                }
            }
        '''
        collection_info = []
        for collection_id in st.session_state.collections:
            variables = {'identifier': collection_id}
            response = st.session_state.session.post(
                st.session_state.API_URL,
                json = {'query': collection_info_query, 'variables': variables}
            )
            queries_sent.append({'query': collection_info_query, 'variables': variables})
            data = response.json()['data']['collection']
            collection_info.append({'identifier': collection_id, 'title': data['title'], 'description': data['description']})

        st.subheader('Selected Collections')
        st.dataframe(pd.DataFrame(collection_info))



        # Retrieves all items within each selected collection
        items_total_query = '''
            query($full_identifier: String!) {
                items(full_identifier: $full_identifier) {
                    total
                }
            }
        '''
        items_page_query = '''
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
        for collection_id in st.session_state.collections:
            variables = {'full_identifier': collection_id}
            response = st.session_state.session.post(
                st.session_state.API_URL,
                json = {'query': items_total_query, 'variables': variables}
            )
            queries_sent.append({'query': items_total_query, 'variables': variables})

            total_items = response.json()['data']['items']['total']
            pages = total_items // st.session_state.PAGE_LIMIT
            if ((total_items % st.session_state.PAGE_LIMIT) != 0): pages = pages + 1

            for page in range(pages):
                variables = {'limit': st.session_state.PAGE_LIMIT, 'page': (page + 1), 'full_identifier': collection_id}
                response = st.session_state.session.post(
                    st.session_state.API_URL,
                    json = {'query': items_page_query, 'variables': variables}
                )
                queries_sent.append({'query': items_page_query, 'variables': variables})
                for result in response.json()['data']['items']['results']:
                    result['collection'] = collection_id
                    collection_items.append(result)

        st.subheader('Items in Selected Collection(s)')
        st.dataframe(pd.DataFrame(collection_items))

        if show_query:
            st.subheader('GraphQL Queries Sent')
            for sent in queries_sent:
                st.code(sent['query'], language = 'graphql')
                st.json(sent['variables'])



    # Retrieves specific item information, limited to items in the selected collection(s)
    st.subheader('Specific Item Information')
    item_options = [item['full_identifier'] for item in collection_items]

    if (len(item_options) == 0): st.info('Select one or more collections above to choose an item.')
    else:
        if ('item' in st.session_state and st.session_state.item in item_options): st.session_state.item = st.selectbox('Item Full Identifier:', item_options, item_options.index(st.session_state.item), placeholder = 'Select Item Full Identifier')
        else: st.session_state.item = st.selectbox('Item Full Identifier:', item_options, None, placeholder = 'Select Item Full Identifier')

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

            if show_query:
                st.subheader('GraphQL Query Sent')
                st.code(query, language = 'graphql')
                st.json(variables)

            st.write('All available item information (sub object information simplified):')
            st.dataframe(pd.DataFrame(response.json()['data']))
