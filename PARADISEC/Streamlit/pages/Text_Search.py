import streamlit as st

if ('email' not in st.session_state or 'password' not in st.session_state): st.header('Login First!')
elif (st.session_state.email == '' or st.session_state.password == ''): st.header('Login First!')
else:
    # TESTING
    # query = '''
    #     query {
    #         item(fullIdentifier: "MMT1-20170703a") {
    #             permalink
    #             essences_count
    #             essences {
    #                 filename
    #                 mimetype
    #                 permalink
    #             }
    #         }
    #     }
    # '''
    # response = st.session_state.session.post(
    #     'https://admin-catalog.paradisec.org.au/graphql',
    #     json={'query': query},
    #     headers={
    #         'Content-Type': 'application/json',
    #         'X-CSRF-Token': st.session_state.csrf_token
    #     }
    # )

    # st.write(response.json())

    # query = '''
    #     query {
    #         items {
    #             total
    #         }
    #     }
    #     '''
    # response = st.session_state.session.post(
    #     'https://admin-catalog.paradisec.org.au/graphql',
    #     json={'query': query},
    #     headers={
    #         'Content-Type': 'application/json',
    #         'X-CSRF-Token': st.session_state.csrf_token
    #     }
    # )

    # total_items = response.json()['data']['items']['total']
    # pages = total_items // st.session_state.enforced_page_limit
    # if ((total_items % st.session_state.enforced_page_limit) != 0): pages = pages + 1



    # all_mimetypes = {}
    # no_mimetype_counter = 0
    # for page in range(pages):
    #     query = '''
    #         query($page: Int!, $limit: Int!) {
    #             items(limit: $limit, page: $page) {
    #                 results {
    #                     essences {
    #                         mimetype
    #                     }
    #                 }
    #             }
    #         }
    #     '''
    #     variables = {'limit': st.session_state.enforced_page_limit, 'page': (page + 1)}
    #     response = st.session_state.session.post(
    #         'https://admin-catalog.paradisec.org.au/graphql',
    #         json={'query': query, 'variables': variables},
    #         headers={
    #             'Content-Type': 'application/json',
    #             'X-CSRF-Token': st.session_state.csrf_token
    #         }
    #     )
    #     for result in response.json()['data']['items']['results']:
    #         for essence in result['essences']:
    #             if (essence['mimetype'] == None): no_mimetype_counter = no_mimetype_counter + 1
    #             else:
    #                 value = all_mimetypes.get(essence['mimetype'])
    #                 if (value != None): all_mimetypes.update({essence['mimetype']: (value + 1)})
    #                 else: all_mimetypes.update({essence['mimetype']: 1})
    #     st.write('Processing...Page Completed...')

    # st.subheader('Processing Completed!')
    # st.write(no_mimetype_counter)
    # st.write(all_mimetypes)
    # for mimetype in all_mimetypes.keys(): st.write(mimetype)



    # query = '''
    #     query {
    #         items {
    #             total
    #         }
    #     }
    #     '''
    # response = st.session_state.session.post(
    #     'https://admin-catalog.paradisec.org.au/graphql',
    #     json={'query': query},
    #     headers={
    #         'Content-Type': 'application/json',
    #         'X-CSRF-Token': st.session_state.csrf_token
    #     }
    # )

    # total_items = response.json()['data']['items']['total']
    # pages = total_items // st.session_state.enforced_page_limit
    # if ((total_items % st.session_state.enforced_page_limit) != 0): pages = pages + 1

    # all_languages = {}
    # for page in range(pages):
    #     query = '''
    #         query($page: Int!, $limit: Int!) {
    #             items(limit: $limit, page: $page) {
    #                 results {
    #                     content_languages {
    #                         name
    #                     }
    #                     subject_languages {
    #                         name
    #                     }
    #                 }
    #             }
    #         }
    #     '''
    #     variables = {'limit': st.session_state.enforced_page_limit, 'page': (page + 1)}
    #     response = st.session_state.session.post(
    #         'https://admin-catalog.paradisec.org.au/graphql',
    #         json={'query': query, 'variables': variables},
    #         headers={
    #             'Content-Type': 'application/json',
    #             'X-CSRF-Token': st.session_state.csrf_token
    #         }
    #     )
    #     for result in response.json()['data']['items']['results']:
    #         languages = {}
    #         for language in result['content_languages']: languages.update({language['name']: 0})
    #         for language in result['subject_languages']: languages.update({language['name']: 0})
    #         for name in languages.keys():
    #             value = all_languages.get(name)
    #             if (value != None): all_languages.update({name: (value + 1)})
    #             else: all_languages.update({name: 1})
    #     st.write('Processing...Page Completed...')

    # st.subheader('Processing Completed!')
    # for name in sorted(all_languages.keys()): st.write(name)



    # query = '''
    #     query {
    #         items {
    #             total
    #         }
    #     }
    #     '''
    # response = st.session_state.session.post(
    #     'https://admin-catalog.paradisec.org.au/graphql',
    #     json={'query': query},
    #     headers={
    #         'Content-Type': 'application/json',
    #         'X-CSRF-Token': st.session_state.csrf_token
    #     }
    # )

    # total_items = response.json()['data']['items']['total']
    # pages = total_items // st.session_state.enforced_page_limit
    # if ((total_items % st.session_state.enforced_page_limit) != 0): pages = pages + 1

    # all_collection_ids = {}
    # for page in range(pages):
    #     query = '''
    #         query($page: Int!, $limit: Int!) {
    #             items(limit: $limit, page: $page) {
    #                 results {
    #                     collection {
    #                         identifier
    #                     }
    #                 }
    #             }
    #         }
    #     '''
    #     variables = {'limit': st.session_state.enforced_page_limit, 'page': (page + 1)}
    #     response = st.session_state.session.post(
    #         'https://admin-catalog.paradisec.org.au/graphql',
    #         json={'query': query, 'variables': variables},
    #         headers={
    #             'Content-Type': 'application/json',
    #             'X-CSRF-Token': st.session_state.csrf_token
    #         }
    #     )
    #     for result in response.json()['data']['items']['results']:
    #         value = all_collection_ids.get(result['collection']['identifier'])
    #         if (value != None): all_collection_ids.update({result['collection']['identifier']: (value + 1)})
    #         else: all_collection_ids.update({result['collection']['identifier']: 1})
    #     st.write('Processing...Page Completed...')

    # st.subheader('Processing Completed!')
    # for id in sorted(all_collection_ids.keys()): st.write(id)



    # query = '''
    #     query {
    #         items {
    #             total
    #         }
    #     }
    #     '''
    # response = st.session_state.session.post(
    #     'https://admin-catalog.paradisec.org.au/graphql',
    #     json={'query': query},
    #     headers={
    #         'Content-Type': 'application/json',
    #         'X-CSRF-Token': st.session_state.csrf_token
    #     }
    # )

    # total_items = response.json()['data']['items']['total']
    # pages = total_items // st.session_state.enforced_page_limit
    # if ((total_items % st.session_state.enforced_page_limit) != 0): pages = pages + 1

    # all_collectors = {}
    # all_regions = {}
    # all_universities = {}
    # for page in range(pages):
    #     query = '''
    #         query($page: Int!, $limit: Int!) {
    #             items(limit: $limit, page: $page) {
    #                 results {
    #                     collector {
    #                         name
    #                     }
    #                     region
    #                     university {
    #                         name
    #                     }
    #                 }
    #             }
    #         }
    #     '''
    #     variables = {'limit': st.session_state.enforced_page_limit, 'page': (page + 1)}
    #     response = st.session_state.session.post(
    #         'https://admin-catalog.paradisec.org.au/graphql',
    #         json={'query': query, 'variables': variables},
    #         headers={
    #             'Content-Type': 'application/json',
    #             'X-CSRF-Token': st.session_state.csrf_token
    #         }
    #     )
    #     for result in response.json()['data']['items']['results']:
    #         if (result['collector'] != None): all_collectors.update({result['collector']['name']: 1})
    #         if (result['region'] != None): all_regions.update({result['region']: 1})
    #         if (result['university'] != None): all_universities.update({result['university']['name']: 1})
    #     st.write('Processing...Page Completed...')

    # st.header('Processing Completed!')
    # st.subheader('Collectors:')
    # for item in sorted(all_collectors.keys()): st.write(item)
    # st.subheader('Regions:')
    # for item in sorted(all_regions.keys()): st.write(item)
    # st.subheader('Universities:')
    # for item in sorted(all_universities.keys()): st.write(item)



    # query = '''
    #     query {
    #         items {
    #             total
    #         }
    #     }
    #     '''
    # response = st.session_state.session.post(
    #     'https://admin-catalog.paradisec.org.au/graphql',
    #     json={'query': query},
    #     headers={
    #         'Content-Type': 'application/json',
    #         'X-CSRF-Token': st.session_state.csrf_token
    #     }
    # )

    # total_items = response.json()['data']['items']['total']
    # pages = total_items // st.session_state.enforced_page_limit
    # if ((total_items % st.session_state.enforced_page_limit) != 0): pages = pages + 1

    # all_item_identifiers = []
    # for page in range(pages):
    #     query = '''
    #         query($page: Int!, $limit: Int!) {
    #             items(limit: $limit, page: $page) {
    #                 results {
    #                     full_identifier
    #                 }
    #             }
    #         }
    #     '''
    #     variables = {'limit': st.session_state.enforced_page_limit, 'page': (page + 1)}
    #     response = st.session_state.session.post(
    #         'https://admin-catalog.paradisec.org.au/graphql',
    #         json={'query': query, 'variables': variables},
    #         headers={
    #             'Content-Type': 'application/json',
    #             'X-CSRF-Token': st.session_state.csrf_token
    #         }
    #     )
    #     for result in response.json()['data']['items']['results']: all_item_identifiers.append(result['full_identifier'])
    #     st.write('Processing...Page Completed...')

    # st.subheader('Processing Completed!')
    # st.write("|".join(all_item_identifiers))




    st.header('Filters')
    # Required language filter
    if ('filter_language' in st.session_state and st.session_state.filter_language != None): st.session_state.filter_language = st.selectbox('Language:', st.session_state.languages_list, st.session_state.languages_list.index(st.session_state.filter_language))
    else: st.session_state.filter_language = st.selectbox('Language:', st.session_state.languages_list, None, placeholder='Select Language (Required)')

    if (st.session_state.filter_language != None):
        # Additional optional filters
        if ('filter_collection' in st.session_state and st.session_state.filter_collection != None): st.session_state.filter_collection = st.selectbox('Collection ID:', st.session_state.collection_identifiers_list, st.session_state.collection_identifiers_list.index(st.session_state.filter_collection))
        else: st.session_state.filter_collection = st.selectbox('Collection ID:', st.session_state.collection_identifiers_list, None, placeholder='Select Collection Identifier (Optional)')

        # BUG Filtering by collector_name has no effect
        # if ('filter_collector' in st.session_state and st.session_state.filter_collector != None): st.session_state.filter_collector = st.selectbox("Collector's Name:", st.session_state.collectors_list, st.session_state.collectors_list.index(st.session_state.filter_collector))
        # else: st.session_state.filter_collector = st.selectbox("Collector's Name:", st.session_state.collectors_list, None, placeholder="Select Collector's Name (Optional)")

        if ('filter_region' in st.session_state and st.session_state.filter_region != None): st.session_state.filter_region = st.selectbox('Region:', st.session_state.regions_list, st.session_state.regions_list.index(st.session_state.filter_region))
        else: st.session_state.filter_region = st.selectbox('Region:', st.session_state.regions_list, None, placeholder='Select Region (Optional)')

        # BUG Filtering by university_name has no effect
        # if ('filter_university' in st.session_state and st.session_state.filter_university != None): st.session_state.filter_university = st.selectbox('University Name:', st.session_state.universities_list, st.session_state.universities_list.index(st.session_state.filter_university))
        # else: st.session_state.filter_university = st.selectbox('University Name:', st.session_state.universities_list, None, placeholder='Select University Name (Optional)')

        # Search parameters
        st.header('Search Parameters')

        search_types = ['Exact', 'Partial', 'Fuzzy', 'Semantic']
        if ('search_type' in st.session_state and st.session_state.search_type != None): st.session_state.search_type = st.selectbox('Search Type:', search_types, search_types.index(st.session_state.search_type))
        else: st.session_state.search_type = st.selectbox('Search Type:', search_types, None, placeholder='Select Type of Search')

        if ('search_text' not in st.session_state): st.session_state.search_text = st.text_input('Search Text:')
        else: st.session_state.search_text = st.text_input('Search Text:', st.session_state.search_text)

        if (st.session_state.search_type != None and st.session_state.search_text != ""):
            if st.button('Search', icon=":material/search:"):
                # TODO Actual search functions
                st.write('In Progress')