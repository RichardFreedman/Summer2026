import streamlit as st
import requests
from urllib.parse import quote

if (st.session_state.logged_in == False): st.header('Login First!')
else:
    # Clears all optional filters
    def clear_filters():
        st.session_state.filter_collection = None
        # st.session_state.filter_collector = None
        st.session_state.filter_region = None
        # st.session_state.filter_university = None

    st.header('Filters')

    # Required language filter
    if ('filter_language' in st.session_state and st.session_state.filter_language != None): st.session_state.filter_language = st.selectbox('Language:', st.session_state.languages_list, st.session_state.languages_list.index(st.session_state.filter_language), placeholder = 'Select Language (Required)')
    else: st.session_state.filter_language = st.selectbox('Language:', st.session_state.languages_list, None, placeholder = 'Select Language (Required)')

    # Additional optional filters
    if ('filter_collection' in st.session_state and st.session_state.filter_collection != None): st.session_state.filter_collection = st.selectbox('Collection ID:', st.session_state.collection_identifiers_list, st.session_state.collection_identifiers_list.index(st.session_state.filter_collection), placeholder = 'Select Collection Identifier (Optional)')
    else: st.session_state.filter_collection = st.selectbox('Collection ID:', st.session_state.collection_identifiers_list, None, placeholder = 'Select Collection Identifier (Optional)')

    # BUG Filtering by collector_name has no effect
    # if ('filter_collector' in st.session_state and st.session_state.filter_collector != None): st.session_state.filter_collector = st.selectbox("Collector's Name:", st.session_state.collectors_list, st.session_state.collectors_list.index(st.session_state.filter_collector), placeholder = "Select Collector's Name (Optional)")
    # else: st.session_state.filter_collector = st.selectbox("Collector's Name:", st.session_state.collectors_list, None, placeholder = "Select Collector's Name (Optional)")

    if ('filter_region' in st.session_state and st.session_state.filter_region != None): st.session_state.filter_region = st.selectbox('Region:', st.session_state.regions_list, st.session_state.regions_list.index(st.session_state.filter_region), placeholder = 'Select Region (Optional)')
    else: st.session_state.filter_region = st.selectbox('Region:', st.session_state.regions_list, None, placeholder = 'Select Region (Optional)')

    # BUG Filtering by university_name has no effect
    # if ('filter_university' in st.session_state and st.session_state.filter_university != None): st.session_state.filter_university = st.selectbox('University Name:', st.session_state.universities_list, st.session_state.universities_list.index(st.session_state.filter_university), placeholder = 'Select University Name (Optional)')
    # else: st.session_state.filter_university = st.selectbox('University Name:', st.session_state.universities_list, None, placeholder = 'Select University Name (Optional)')

    st.button('Clear Optional Filters', on_click = clear_filters, icon = ':material/ink_eraser:')



    # Search parameters
    st.header('Search Parameters')

    search_types = ['Exact', 'Fuzzy', 'Semantic']
    if ('search_type' in st.session_state and st.session_state.search_type != None): st.session_state.search_type = st.selectbox('Search Type:', search_types, search_types.index(st.session_state.search_type), placeholder = 'Select Type of Search')
    else: st.session_state.search_type = st.selectbox('Search Type:', search_types, None, placeholder = 'Select Type of Search')

    if ('search_text' not in st.session_state): st.session_state.search_text = st.text_input('Search Text:')
    else: st.session_state.search_text = st.text_input('Search Text:', st.session_state.search_text)

    if (st.session_state.filter_language != None and st.session_state.search_type != None and st.session_state.search_text != ""):
        if st.button('Search', icon = ':material/search:'):
            st.header('Search Results')

            # Retrieves all items that fit the given parameters and their essences
            query = '''
                query($full_identifier: String, $language: String, $region: String) {
                    items(full_identifier: $full_identifier, language: $language, region: $region) {
                        total
                    }
                }
                '''
            variables = {'full_identifier': st.session_state.filter_collection, 'language': st.session_state.filter_language, 'region': st.session_state.filter_region}
            response = st.session_state.session.post(
                st.session_state.API_URL,
                json = {'query': query, 'variables': variables}
            )

            total_filtered_items = response.json()['data']['items']['total']
            pages = total_filtered_items // st.session_state.PAGE_LIMIT
            if ((total_filtered_items % st.session_state.PAGE_LIMIT) != 0): pages = pages + 1

            filtered_essences = {}
            for page in range(pages):
                query = '''
                    query($page: Int!, $limit: Int!, $full_identifier: String, $language: String, $region: String) {
                        items(limit: $limit, page: $page, full_identifier: $full_identifier, language: $language, region: $region) {
                            results {
                                full_identifier
                                essences {
                                    mimetype
                                    permalink
                                }
                            }
                        }
                    }
                '''
                variables = {'limit': st.session_state.PAGE_LIMIT, 'page': (page + 1), 'full_identifier': st.session_state.filter_collection, 'language': st.session_state.filter_language, 'region': st.session_state.filter_region}
                response = st.session_state.session.post(
                    st.session_state.API_URL,
                    json = {'query': query, 'variables': variables}
                )
                for result in response.json()['data']['items']['results']:
                    essence_info = {}
                    for essence in result['essences']: essence_info.update({essence['permalink']: essence['mimetype']})
                    filtered_essences.update({result['full_identifier']: essence_info})



            # FIXME
            # Removes all essences/items that aren't searchable (e.g. aren't text or model accessible)
            searchable_mimetypes = ['application/pdf', 'text/html', 'text/plain', 'text/rtf', 'text/x-tex']
            unsearchable_items = []
            for key1, value1 in filtered_essences.items():
                unsearchable_essences = []
                for key2, value2 in value1.items():
                    if value2 not in searchable_mimetypes: unsearchable_essences.append(key2)
                for essence in unsearchable_essences: del value1[essence]
                if (len(value1) == 0): unsearchable_items.append(key1)
            for item in unsearchable_items: del filtered_essences[item]

            if (len(filtered_essences) == 0): st.subheader('No searchable files under these parameters!')
            else:
                # Retrieves the bytes from the raw file given the catalog permalink
                def get_raw_file_bytes(permalink):
                    filename = permalink.rsplit('/', 1)[-1]
                    encoded_permalink = quote(permalink, safe='')
                    essence_file_url = f'https://admin-catalog.paradisec.org.au/api/v1/oni/file/{encoded_permalink}'

                    response = requests.get(
                        essence_file_url,
                        params = {'disposition': 'inline', 'filename': filename},
                        headers = {'Authorization': f'Bearer {st.session_state.raw_file_auth_token}'},
                        allow_redirects = True
                    )
                    return response.content

                # TODO pass in files



            # # TODO remove all files with mimetypes without text (keep transcribable audio files?), parse the files and return the results based on search parameters
            # st.subheader('In Progress')



# TODO LLM stuff, eventually will be moved
# from ollama import chat

# # Allows for typewriter effect
# def stream_text(stream):
#     for chunk in stream:
#         content = chunk['message']['content']
#         if content: yield content

# stream = chat(
#     model='llama3.1:8b',
#     messages=[
#         {
#             'role': 'system',
#             'content': 'You are a poet. Respond in rhyme.'
#         },
#         {
#             'role': 'user',
#             'content': 'This is a test. Is this working?'
#         }
#     ],
#     stream=True
# )
# st.write_stream(stream_text(stream))