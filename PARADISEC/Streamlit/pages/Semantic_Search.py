import json
import math
from ollama import chat
import streamlit as st

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

                    # Creating a cleaned and simplified version of the response
                    metadata = {'identifier': response['identifier']}
                    if (response['access_class']): metadata.update({'access_class': response['access_class']})
                    if (response['collector']):
                        if (response['collector']['name']): metadata.update({'collector': response['collector']['name']})
                    if (response['comments']): metadata.update({'comments': response['comments']})
                    if (response['content_languages']):
                        languages = []
                        for language in response['content_languages']: languages.append(language['name'])
                        metadata.update({'content_languages': languages})
                    if (response['countries']):
                        countries = []
                        for country in response['countries']: countries.append(country['name'])
                        metadata.update({'countries': countries})
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
                        metadata.update({'subject_languages': languages})
                    metadata.update({'title': response['title']})
                    if (response['university']): metadata.update({'university': response['university']['name']})

                    collections_metadata.append(metadata)
                return collections_metadata

            collections_metadata = get_collections_metadata()

            collection_parsing_progress_bar = st.progress(0.0, 'Parsing Collections...')
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
                collection_parsing_progress_bar.progress(completion_percent, 'Parsing Collections...')

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
                                {"identifier": "BX21", "title": "Traditional indigenous tales", "comments": "some text are transcriptions of the videos, some are separate entities", "media": "video, text"}]

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

            collection_parsing_progress_bar.progress(1.0, 'Collections Parsed!')

            # TODO Parse through specific items and actually output results



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