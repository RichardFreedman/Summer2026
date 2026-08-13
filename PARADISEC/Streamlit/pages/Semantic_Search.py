import json
import math
from ollama import chat
import random
import streamlit as st
import time

if (st.session_state.logged_in == False): st.header('Login First!')
else:
    st.header('LLM Assisted Search')

    st.text_area('Question / Description:', height = 'content', key = 'search_llm', persist_state = 'session')

    if (st.session_state.search_llm != ""):
        if st.button('Search', icon = ':material/auto_awesome:'):
            # Retrieves all collection metadata that could be helpful for a semantic search
            @st.cache_data
            def get_collections_metadata() -> list:
                collections_metadata = []
                query = '''
                    query($identifier: ID!) {
                        collection(identifier: $identifier) {
                            access_class
                            collector {
                                name
                            }
                            comments
                            content_languages {
                                name
                            }
                            countries {
                                name
                            }
                            description
                            field_of_research {
                                name
                            }
                            grants {
                                funding_body {
                                    name
                                }
                            }
                            identifier
                            media
                            operator {
                                name
                            }
                            region
                            subject_languages {
                                name
                            }
                            title
                            university {
                                name
                            }
                        }
                    }
                '''
                for collection in st.session_state.collection_identifiers_list:
                    variables = {'identifier': collection}
                    response = st.session_state.session.post(
                        st.session_state.API_URL,
                        json = {'query': query, 'variables': variables}
                    ).json()['data']['collection']

                    # Creating a cleaned and simplified version of the collection metadata
                    metadata = {'identifier': response['identifier']}
                    if (response['access_class']): metadata.update({'access_class': response['access_class']})
                    if (response['collector']):
                        if (response['collector']['name']): metadata.update({'collector': response['collector']['name']})
                    if (response['comments']): metadata.update({'comments': response['comments']})
                    if (response['content_languages']):
                        languages = []
                        for language in response['content_languages']: languages.append(language['name'])
                        if (languages): metadata.update({'content_languages': languages})
                    if (response['countries']):
                        countries = []
                        for country in response['countries']: countries.append(country['name'])
                        if (countries): metadata.update({'countries': countries})
                    if (response['description']): metadata.update({'description': response['description']})
                    if (response['field_of_research']): metadata.update({'field_of_research': response['field_of_research']['name']})
                    if (response['grants']):
                        grants = []
                        for grant in response['grants']:
                            if (grant['funding_body']): grants.append(grant['funding_body']['name'])
                        if (grants): metadata.update({'grants': grants})
                    if (response['media']): metadata.update({'media': response['media']})
                    if (response['operator']):
                        if (response['operator']['name']): metadata.update({'operator': response['operator']['name']})
                    if (response['region']): metadata.update({'region': response['region']})
                    if (response['subject_languages']):
                        languages = []
                        for language in response['subject_languages']: languages.append(language['name'])
                        if (languages): metadata.update({'subject_languages': languages})
                    metadata.update({'title': response['title']})
                    if (response['university']): metadata.update({'university': response['university']['name']})

                    collections_metadata.append(metadata)
                    time.sleep(0.2)
                return collections_metadata

            st.caption('Gathering Collection Metadata...')

            collections_metadata = get_collections_metadata()
            random.shuffle(collections_metadata) # Helps prevent the model from only pulling from related collections in a batch

            collection_parsing_progress_bar = st.progress(0.0, 'Searching Through Collections...')
            chat_percent = 1.0 / (math.ceil(len(collections_metadata) / 40) + 1)
            completion_percent = 0.0

            # Makes an initial pass through all the collection metadata in batches to maintain memory/coherency
            collections_metadata_batches = [collections_metadata[i:i + 40] for i in range(0, len(collections_metadata), 40)]
            candidate_collections = []
            for batch in collections_metadata_batches:
                chat_response = chat(
                    'llama3.1:8b',
                    [
                        {
                            'role': 'system',
                            'content': '''
                                You are a Collection Relevance Filter for a semantic search system, screening
                                ONE SUBSET of a larger collection set against a user query. Other subsets are
                                being screened separately, so it is normal and expected to return few or even
                                zero collections if nothing in THIS subset relates to the query.

                                TASK
                                You are given:
                                1. A set of "collections" — each has a unique identifier and many other fields
                                containing various pieces of metadata.
                                2. A user's query or description of what they are looking for.

                                Your job is to identify which collections might contain items relevant to the
                                user's query, based ONLY on the collection metadata provided. This is a coarse
                                first-pass filter, not a final answer — you are narrowing down candidates for
                                a more detailed search later. Do not try to answer the user's query itself.

                                Each collection is a JSON object containing an "identifier" field (its unique
                                ID) plus metadata fields such as title, description, and others. Always
                                return the value of the "identifier" field for each relevant collection.
                                Never return a title, description, or any other field value in its place.

                                RULES
                                - Only use the collection identifiers given to you. Never invent, alter, or
                                abbreviate an identifier.
                                - Select collections with some chance of relating to the query. Do not require
                                certainty, and do not include collections that are clearly and absolutely unrelated.
                                - The "title" and "description" fields will be most important for semantic matching.
                                - Return AT MOST 5 collections. If more than 5 seem plausible, return only
                                the 5 most likely. Do not limit returns otherwise.
                                - Never explain your reasoning. Never include any text, markdown, or
                                commentary outside the required JSON object.
                                - Some queries reference a specific value that could match a metadata field
                                directly: a university, collector, operator, region, country, or language.
                                When this happens, treat any collection whose corresponding field contains
                                an exact or extremely close match as relevant, even if nothing else about that
                                collection seems related to the query.

                                OUTPUT FORMAT
                                Respond with ONLY valid JSON, matching exactly this structure:
                                {"collections": ["<identifier>", "<identifier>"]}
                            '''
                        },
                        {
                            'role': 'user',
                            'content': f'''
                                Collections:

                                ```json
                                {json.dumps(batch)}
                                ```

                                User query:
                                """
                                {st.session_state.search_llm}
                                """

                                Return the JSON object now.
                            '''
                        }
                    ],
                    format = {
                        'type': 'object',
                        'properties': {
                            'collections': {
                                'type': 'array',
                                'items': {
                                    'type': 'string',
                                    'enum': [metadata['identifier'] for metadata in batch]
                                },
                                'maxItems': 5,
                                'uniqueItems': True
                            }
                        },
                        'required': ['collections']
                    },
                    options = {'temperature': 0.2, 'num_ctx': 8192}
                )
                chat_result = json.loads(chat_response['message']['content'])
                candidate_collections.extend(collection for collection in chat_result['collections'] if collection in st.session_state.collection_identifiers_list)

                completion_percent = completion_percent + chat_percent
                collection_parsing_progress_bar.progress(completion_percent, 'Searching Through Collections...')

            # Makes a last pass refining the candidate collections if needed
            if len(candidate_collections) <= 3: matched_collections = candidate_collections
            else:
                candidate_collections_metadata = [metadata for metadata in collections_metadata if metadata['identifier'] in candidate_collections]
                chat_response = chat(
                    'llama3.1:8b',
                    [
                        {
                            'role': 'system',
                            'content': '''
                                You are a Collection Relevance Filter for a semantic search system.

                                You are working with metadata from PARADISEC, which is a digital archive of
                                records of some of the many small cultures and languages of the world. Within
                                their catalog is digitized audio, text and visual material.

                                TASK
                                You are given:
                                1. A set of "collections" — each has a unique identifier and many other fields
                                containing various pieces of metadata.
                                2. A user's query or description of what they are looking for.

                                Your job is to identify which collections might contain items relevant to the
                                user's query, based ONLY on the collection metadata provided. This is a coarse
                                first-pass filter, not a final answer — you are narrowing down candidates for
                                a more detailed search later. Do not try to answer the user's query itself.

                                Each collection is a JSON object containing an "identifier" field (its unique
                                ID) plus metadata fields such as title, description, and others. Always
                                return the value of the "identifier" field for each relevant collection.
                                Never return a title, description, or any other field value in its place.

                                RULES
                                - Only use the collection identifiers given to you. Never invent, alter, or
                                abbreviate an identifier.
                                - Select collections with some chance of relating to the query. Do not require
                                certainty, and do not include collections that are clearly and absolutely unrelated.
                                - The "title" and "description" fields will be most important for semantic matching.
                                - Return AT LEAST 3 collections.
                                - Return AT MOST 15 collections. If more than 15 seem plausible, return only
                                the 15 most likely. Do not limit returns otherwise.
                                - Never explain your reasoning. Never include any text, markdown, or
                                commentary outside the required JSON object.
                                - Some queries reference a specific value that could match a metadata field
                                directly: a university, collector, operator, region, country, or language.
                                When this happens, treat any collection whose corresponding field contains
                                an exact or extremely close match as relevant, even if nothing else about that
                                collection seems related to the query.

                                OUTPUT FORMAT
                                Respond with ONLY valid JSON, matching exactly this structure:
                                {"collections": ["<identifier>", "<identifier>"]}

                                EXAMPLES (illustrative only — real inputs will vary in field coverage, collection
                                count, and how many are relevant; do NOT treat these ratios as targets to replicate)

                                EXAMPLE 1

                                Collections:
                                [{"identifier": "AGB", "title": "Field recordings of ceremonial songs", "content_languages": ["Arrernte"], "media": "audio", "region": "Central Australia"},
                                {"identifier": "EDF", "title": "Contemporary jazz performance archive", "collector": "J. Alvarez", "media": "audio"},
                                {"identifier": "ZMT1", "title": "Oral histories on customary land management", "description": "Interviews with community elders on traditional land use.", "subject_languages": ["Kaurna"], "field_of_research": "Anthropology"},
                                {"identifier": "RDSQ08", "title": "Botanical survey photographs", "field_of_research": "Botany", "media": "image"},
                                {"identifier": "BX21", "title": "Traditional indigenous tales", "comments": "some texts are transcriptions of the videos, some are separate entities", "media": "video, text"}]

                                User query: "recordings of Aboriginal languages and songs"

                                Correct output:
                                {"collections": ["AGB", "ZMT1", "BX21"]}

                                EXAMPLE 2

                                Collections:
                                [{"identifier": "BAR", "title": "Songs and translations of the Kuni language", "university": "University of Sydney"},
                                {"identifier": "MMA", "title": "Migratory practices of the 1800s", "university": "University of Melbourne"},
                                {"identifier": "PLO2", "title": "Interviews of Aboriginal leaders", "university": "University of Sydney"},
                                {"identifier": "STV", "title": "Annual indigenous ceremonies", "comments": "Digitized in partnership with the University of Sydney's linguistics department", "media": "video, text"},
                                {"identifier": "LPM31", "title": "Botanical variety analysis", "field_of_research": "Botany", "operator": "Queensland Herbarium"}]

                                User query: "materials from the University of Sydney"

                                Correct output:
                                {"collections": ["BAR", "PLO2", "STV"]}
                            '''
                        },
                        {
                            'role': 'user',
                            'content': f'''
                                Collections:

                                ```json
                                {json.dumps(candidate_collections_metadata)}
                                ```

                                User query:
                                """
                                {st.session_state.search_llm}
                                """

                                Return the JSON object now.
                            '''
                        }
                    ],
                    format = {
                        'type': 'object',
                        'properties': {
                            'collections': {
                                'type': 'array',
                                'items': {
                                    'type': 'string',
                                    'enum': [metadata['identifier'] for metadata in candidate_collections_metadata]
                                },
                                'minItems': 3,
                                'maxItems': 15,
                                'uniqueItems': True
                            }
                        },
                        'required': ['collections']
                    },
                    options = {'temperature': 0.2, 'num_ctx': 16384}
                )
                chat_result = json.loads(chat_response['message']['content'])
                matched_collections = [collection for collection in chat_result['collections'] if collection in candidate_collections]

            collection_parsing_progress_bar.progress(1.0, 'Collections Searched!')

            # Retrieves the metadata for all the items within the matched collections
            st.caption('Gathering Item Metadata...')

            items_metadata = []
            for collection in matched_collections:
                query = '''
                    query($full_identifier: String!) {
                        items(full_identifier: $full_identifier) {
                            total
                        }
                    }
                '''
                variables = {'full_identifier': collection}
                response = st.session_state.session.post(
                    st.session_state.API_URL,
                    json = {'query': query, 'variables': variables}
                )

                total_items = response.json()['data']['items']['total']
                pages = math.ceil(total_items / st.session_state.PAGE_LIMIT)

                collection_items_metadata = []
                for page in range(pages):
                    query = '''
                        query($limit: Int!, $page: Int!, $full_identifier: String!) {
                            items(limit: $limit, page: $page, full_identifier: $full_identifier) {
                                results {
                                    access_class
                                    born_digital
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
                                    full_identifier
                                    ingest_notes
                                    item_agents {
                                        role_name
                                        user_name
                                    }
                                    language
                                    operator {
                                        name
                                    }
                                    original_media
                                    originated_on
                                    originated_on_narrative
                                    received_on
                                    region
                                    subject_languages {
                                        name
                                    }
                                    title
                                    university {
                                        name
                                    }
                                    updated_at
                                }
                            }
                        }
                    '''
                    variables = {'limit': st.session_state.PAGE_LIMIT, 'page': (page + 1), 'full_identifier': collection}
                    response = st.session_state.session.post(
                        st.session_state.API_URL,
                        json = {'query': query, 'variables': variables}
                    ).json()['data']['items']['results']

                    for result in response:
                        # Creating a cleaned and simplified version of the item metadata
                        metadata = {'full_identifier': result['full_identifier']}
                        if (result['access_class']): metadata.update({'access_class': result['access_class']})
                        if (result['born_digital'] != None): metadata.update({'born_digital': result['born_digital']})
                        if (result['collector']['name']): metadata.update({'collector': result['collector']['name']})
                        if (result['content_languages']):
                            languages = []
                            for language in result['content_languages']: languages.append(language['name'])
                            if (languages): metadata.update({'content_languages': languages})
                        if (result['countries']):
                            countries = []
                            for country in result['countries']: countries.append(country['name'])
                            if (countries): metadata.update({'countries': countries})
                        if (result['created_at']): metadata.update({'created_at': result['created_at']})
                        if (result['data_categories']):
                            categories = []
                            for category in result['data_categories']: categories.append(category['name'])
                            if (categories): metadata.update({'data_categories': categories})
                        if (result['data_types']):
                            types = []
                            for type in result['data_types']: types.append(type['name'])
                            if (types): metadata.update({'data_types': types})
                        if (result['description']): metadata.update({'description': result['description']})
                        if (result['dialect']): metadata.update({'dialect': result['dialect']})
                        if (result['digitised_on']): metadata.update({'digitised_on': result['digitised_on']})
                        if (result['discourse_type']): metadata.update({'discourse_type': result['discourse_type']['name']})
                        if (result['ingest_notes']): metadata.update({'ingest_notes': result['ingest_notes']})
                        if (result['item_agents']):
                            agents = []
                            for agent in result['item_agents']:
                                if (agent['role_name'] and agent['user_name']): agents.append(f'{agent['role_name']}: {agent['user_name']}')
                            if (agents): metadata.update({'item_agents': agents})
                        if (result['language']): metadata.update({'language': result['language']})
                        if (result['operator']):
                            if (result['operator']['name']): metadata.update({'operator': result['operator']['name']})
                        if (result['original_media']): metadata.update({'original_media': result['original_media']})
                        if (result['originated_on']): metadata.update({'originated_on': result['originated_on']})
                        if (result['originated_on_narrative']): metadata.update({'originated_on_narrative': result['originated_on_narrative']})
                        if (result['received_on']): metadata.update({'received_on': result['received_on']})
                        if (result['region']): metadata.update({'region': result['region']})
                        if (result['subject_languages']):
                            languages = []
                            for language in result['subject_languages']: languages.append(language['name'])
                            if (languages): metadata.update({'subject_languages': languages})
                        if (result['title']): metadata.update({'title': result['title']})
                        if (result['university']): metadata.update({'university': result['university']['name']})
                        if (result['updated_at']): metadata.update({'updated_at': result['updated_at']})

                        items_metadata.append(metadata)

                    time.sleep(0.2)

            random.shuffle(items_metadata) # Helps prevent the model from only pulling items from the same collection in a batch

            item_parsing_progress_bar = st.progress(0.0, 'Searching Through Items...')
            chat_percent = 1.0 / (math.ceil(len(items_metadata) / 40) + 1)
            completion_percent = 0.0

            # Makes an initial pass through all the item metadata in batches to maintain memory/coherency
            items_metadata_batches = [items_metadata[i:i + 40] for i in range(0, len(items_metadata), 40)]
            candidate_items = []
            for batch in items_metadata_batches:
                chat_response = chat(
                    'llama3.1:8b',
                    [
                        {
                            'role': 'system',
                            'content': '''
                                You are an Item Relevance Filter for a semantic search system, screening
                                ONE SUBSET of a larger item set against a user query. Other subsets are
                                being screened separately, so it is normal and expected to return few or even
                                zero items if nothing in THIS subset relates to the query.

                                TASK
                                You are given:
                                1. A set of "items" — each has a unique full_identifier and many other fields
                                containing various pieces of metadata.
                                2. A user's query or description of what they are looking for.

                                Your job is to identify which items might be relevant to the user's query,
                                based ONLY on the item metadata provided. This is not a final answer — you
                                are only identifying possible candidates. Do not try to answer the user's
                                query itself.

                                Each item is a JSON object containing a "full_identifier" field (its unique
                                ID) plus metadata fields such as title, description, and others. Always
                                return the value of the "full_identifier" field for each relevant item.
                                Never return a title, description, or any other field value in its place.

                                RULES
                                - Only use the item full_identifiers given to you. Never invent, alter, or
                                abbreviate a full_identifier.
                                - Select items with some chance of relating to the query. Do not require
                                certainty, and do not include items that are clearly and absolutely unrelated.
                                - The "title" and "description" fields will be most important for semantic matching.
                                - Return AT MOST 5 items. If more than 5 seem plausible, return only
                                the 5 most likely. Do not limit returns otherwise.
                                - Never explain your reasoning. Never include any text, markdown, or
                                commentary outside the required JSON object.
                                - Some queries reference a specific value that could match a metadata field
                                directly: a university, collector, operator, region, country, or language.
                                When this happens, treat any item whose corresponding field contains
                                an exact or extremely close match as relevant, even if nothing else about that
                                item seems related to the query.

                                OUTPUT FORMAT
                                Respond with ONLY valid JSON, matching exactly this structure:
                                {"items": ["<full_identifier>", "<full_identifier>"]}
                            '''
                        },
                        {
                            'role': 'user',
                            'content': f'''
                                Items:

                                ```json
                                {json.dumps(batch)}
                                ```

                                User query:
                                """
                                {st.session_state.search_llm}
                                """

                                Return the JSON object now.
                            '''
                        }
                    ],
                    format = {
                        'type': 'object',
                        'properties': {
                            'items': {
                                'type': 'array',
                                'items': {
                                    'type': 'string',
                                    'enum': [metadata['full_identifier'] for metadata in batch]
                                },
                                'maxItems': 5,
                                'uniqueItems': True
                            }
                        },
                        'required': ['items']
                    },
                    options = {'temperature': 0.2, 'num_ctx': 8192}
                )
                chat_result = json.loads(chat_response['message']['content'])
                candidate_items.extend(item for item in chat_result['items'] if item in st.session_state.item_identifiers_list)

                completion_percent = completion_percent + chat_percent
                item_parsing_progress_bar.progress(completion_percent, 'Searching Through Items...')

            # Makes a last pass refining the candidate items if needed
            if len(candidate_items) <= 3: matched_items = candidate_items
            else:
                candidate_items_metadata = [metadata for metadata in items_metadata if metadata['full_identifier'] in candidate_items]
                chat_response = chat(
                    'llama3.1:8b',
                    [
                        {
                            'role': 'system',
                            'content': '''
                                You are an Item Relevance Filter for a semantic search system.

                                You are working with metadata from PARADISEC, which is a digital archive of
                                records of some of the many small cultures and languages of the world. Within
                                their catalog is digitized audio, text and visual material.

                                TASK
                                You are given:
                                1. A set of "items" — each has a unique full_identifier and many other fields
                                containing various pieces of metadata.
                                2. A user's query or description of what they are looking for.

                                Your job is to identify which items might be relevant to the user's query,
                                based ONLY on the item metadata provided. This is not a final answer — you
                                are only identifying possible candidates. Do not try to answer the user's
                                query itself.

                                Each item is a JSON object containing a "full_identifier" field (its unique
                                ID) plus metadata fields such as title, description, and others. Always
                                return the value of the "full_identifier" field for each relevant item.
                                Never return a title, description, or any other field value in its place.

                                RULES
                                - Only use the item full_identifiers given to you. Never invent, alter, or
                                abbreviate a full_identifier.
                                - Select items with some chance of relating to the query. Do not require
                                certainty, and do not include items that are clearly and absolutely unrelated.
                                - The "title" and "description" fields will be most important for semantic matching.
                                - Return AT LEAST 3 items.
                                - Return AT MOST 15 items. If more than 15 seem plausible, return only
                                the 15 most likely. Do not limit returns otherwise.
                                - Never explain your reasoning. Never include any text, markdown, or
                                commentary outside the required JSON object.
                                - Some queries reference a specific value that could match a metadata field
                                directly: a university, collector, operator, region, country, or language.
                                When this happens, treat any item whose corresponding field contains
                                an exact or extremely close match as relevant, even if nothing else about that
                                item seems related to the query.

                                OUTPUT FORMAT
                                Respond with ONLY valid JSON, matching exactly this structure:
                                {"items": ["<full_identifier>", "<full_identifier>"]}

                                EXAMPLES (illustrative only — real inputs will vary in field coverage, item
                                count, and how many are relevant; do NOT treat these ratios as targets to replicate)

                                EXAMPLE 1

                                Items:
                                [{"full_identifier": "AGB1-CS_20180612_ceremony", "title": "Field recordings of ceremonial songs", "content_languages": ["Arrernte"], "original_media": "audio", "region": "Central Australia"},
                                {"full_identifier": "EDF3-JZ_20190304_session", "title": "Contemporary jazz performance recording", "item_agents": ["recorder: J. Alvarez"], "original_media": "audio"},
                                {"full_identifier": "ZMT1-OH_20200811_elders", "title": "Oral history on customary land management", "description": "Interview with community elder on traditional land use.", "subject_languages": ["Kaurna"], "discourse_type": "narrative"},
                                {"full_identifier": "RDSQ08-BOT_20170922_survey", "title": "Botanical survey photograph set", "original_media": "image"},
                                {"full_identifier": "BX21-TL_20210505_tales", "title": "Traditional indigenous tale", "ingest_notes": "some texts are transcriptions of the videos, some are separate entities", "original_media": "video, text"}]

                                User query: "recordings of Aboriginal languages and songs"

                                Correct output:
                                {"items": ["AGB1-CS_20180612_ceremony", "ZMT1-OH_20200811_elders", "BX21-TL_20210505_tales"]}

                                EXAMPLE 2

                                Items:
                                [{"full_identifier": "BAR1-KN_20150214_songs", "title": "Songs and translations of the Kuni language", "university": "University of Sydney"},
                                {"full_identifier": "MMA2-MP_18990601_practices", "title": "Migratory practices of the 1800s", "university": "University of Melbourne"},
                                {"full_identifier": "PLO2-INT_20160730_leaders", "title": "Interview of Aboriginal leader", "university": "University of Sydney"},
                                {"full_identifier": "STV1-CER_20140912_annual", "title": "Annual indigenous ceremony", "ingest_notes": "Digitised in partnership with the University of Sydney's linguistics department", "original_media": "video, text"},
                                {"full_identifier": "LPM31-BOT_20191203_variety", "title": "Botanical variety analysis", "operator": "Queensland Herbarium"}]

                                User query: "materials from the University of Sydney"

                                Correct output:
                                {"items": ["BAR1-KN_20150214_songs", "PLO2-INT_20160730_leaders", "STV1-CER_20140912_annual"]}
                            '''
                        },
                        {
                            'role': 'user',
                            'content': f'''
                                Items:

                                ```json
                                {json.dumps(candidate_items_metadata)}
                                ```

                                User query:
                                """
                                {st.session_state.search_llm}
                                """

                                Return the JSON object now.
                            '''
                        }
                    ],
                    format = {
                        'type': 'object',
                        'properties': {
                            'items': {
                                'type': 'array',
                                'items': {
                                    'type': 'string',
                                    'enum': [metadata['full_identifier'] for metadata in candidate_items_metadata]
                                },
                                'minItems': 3,
                                'maxItems': 15,
                                'uniqueItems': True
                            }
                        },
                        'required': ['items']
                    },
                    options = {'temperature': 0.2, 'num_ctx': 16384}
                )
                chat_result = json.loads(chat_response['message']['content'])
                matched_items = [item for item in chat_result['items'] if item in candidate_items]

            item_parsing_progress_bar.progress(1.0, 'Items Searched!')

            st.caption('Preparing Response...')

            matched_items_metadata = [metadata for metadata in items_metadata if metadata['full_identifier'] in matched_items]

            # Generates an actual response that gives each matched item's full_identifier as well as some explanation of why it matched
            stream = chat(
                model = 'llama3.1:8b',
                messages = [
                    {
                        'role': 'system',
                        'content': '''
                            You are explaining, for a semantic search system, why each item in a list
                            was surfaced as a match for a user's query.

                            You are working with metadata from PARADISEC, which is a digital archive of
                            records of some of the many small cultures and languages of the world. Within
                            their catalog is digitized audio, text and visual material.

                            TASK
                            You are given:
                            1. A list of items — each a JSON object with a full_identifier plus
                            metadata fields such as title, description, and others.
                            2. A user's query.

                            For EACH item, in the order given, write a short explanation of why it is
                            a reasonable match for the query, grounded ONLY in the metadata provided.
                            Do not invent facts, dates, names, or content the metadata doesn't state.
                            You are talking to the user directly.

                            FORMAT FOR EACH ITEM
                            Start each item's explanation on its own line with this exact format:
                            ### <full_identifier>
                            <1-5 sentence explanation>

                            Process every item in the list, in order, with no items skipped and no
                            items added. Do not include any text before the first "###" line or after
                            the last item. Do not add a summary, introduction, or conclusion.

                            RULES
                            - Refer to specific fields or values that justify the match (e.g. title
                            wording, a matching language, a matching university).
                            - If the connection is more indirect, say so plainly rather than
                            overstating confidence.
                            - Do not restate the full metadata verbatim — synthesize, don't list.
                            - Do not mention "the metadata", "the JSON", or any implementation detail —
                            write as if describing the item itself to the user.
                        '''
                    },
                    {
                        'role': 'user',
                        'content': f'''
                            Items:
                            ```json
                            {json.dumps(matched_items_metadata)}
                            ```

                            User query:
                            """
                            {st.session_state.search_llm}
                            """

                            Write the explanations now, following the required format exactly.
                        '''
                    }
                ],
                options = {'temperature': 0.3, 'num_ctx': 8192},
                stream = True
            )

            st.write_stream(filter(None, (chunk['message']['content'] for chunk in stream)))

            # NOTE Often returns less results that it probably should, but I don't want to increase the
            # minimum number of returns for fear of overreturning on an extremely specific query; I've done
            # a lot of tweaking and at this point I believe it may just be a limitation of the ability of a
            # local model - it's certainly possible that continually reworking the prompt will eventually reach
            # improved results, but I doubt it will be worth the effort compared to using a much more
            # powerful, assumedly non-local model
            # Also, many items from one collection being returned is still not entirely uncommon