import json
import math
import streamlit as st
import time

if (st.session_state.get('use_dev', False)): st.switch_page('pages/Collection_Information_dev.py')

if (st.session_state.logged_in == False): st.header('Login First!')
else:
    # Gets desired collection from user
    st.header('View Collection Metadata')
    st.selectbox('Collection ID:', st.session_state.collection_identifiers_list, None, key = 'collection', placeholder = 'Select Collection Identifier', persist_state = 'session')

    if (st.session_state.collection != None):
        # Retrieves collection metadata
        query = '''
            query($identifier: ID!) {
                collection(identifier: $identifier) {
                    access_class
                    access_narrative
                    boundaries {
                        east_limit
                        north_limit
                        south_limit
                        west_limit
                    }
                    citation
                    collector {
                        name
                    }
                    comments
                    complete
                    content_languages {
                        name
                        retired
                    }
                    countries {
                        name
                    }
                    description
                    doi
                    doi_json
                    field_of_research {
                        name
                    }
                    grants {
                        funding_body {
                            name
                        }
                        identifier
                    }
                    id
                    identifier
                    media
                    metadata_source
                    operator {
                        name
                    }
                    orthographic_notes
                    permalink
                    region
                    subject_languages {
                        name
                        retired
                    }
                    tape_location
                    title
                    university {
                        name
                    }
                }
            }
        '''
        variables = {'identifier': st.session_state.collection}
        response = st.session_state.session.post(
            st.session_state.API_URL,
            json = {'query': query, 'variables': variables}
        ).json()['data']['collection']

        # Cleans and formats metadata
        information = []
        if (response['access_class']): information.append(f'**Access Class:** {response['access_class']}')
        if (response['access_narrative']): information.append(f'**Access Narrative:** {response['access_narrative']}')
        if (response['boundaries']):information.append(f'**Boundary:**\n- *East Limit:* {response['boundaries']['east_limit']}\n- *North Limit:* {response['boundaries']['north_limit']}\n- *South Limit:* {response['boundaries']['south_limit']}\n- *West Limit:* {response['boundaries']['west_limit']}')
        if (response['citation']): information.append(f'**Citation:** {response['citation']}')
        if (response['collector']):
            if (response['collector']['name']): information.append(f'**Collector:** {response['collector']['name']}')
        if (response['comments']): information.append(f'**Comments:** {response['comments']}')
        if (response['complete'] != None): information.append(f'**Complete:** {response['complete']}')
        if (response['content_languages']):
            languages = []
            for language in response['content_languages']:
                if (language['retired']): languages.append(f'{language['name']} (Retired)')
                else: languages.append(language['name'])
            if (languages): information.append(f'**Content Languages:**\n- {'\n- '.join(languages)}')
        if (response['countries']):
            countries = []
            for country in response['countries']: countries.append(country['name'])
            if (countries): information.append(f'**Countries:**\n- {'\n- '.join(countries)}')
        if (response['description']): information.append(f'**Description:** {response['description']}')
        if (response['doi']): information.append(f'**DOI:** {response['doi']}')
        if (response['doi_json']): information.append(json.loads(response['doi_json']))
        if (response['field_of_research']): information.append(f'**Field of Research:** {response['field_of_research']['name']}')
        if (response['grants']):
            grants = []
            for grant in response['grants']:
                grant_parts = []
                if (grant['identifier']): grant_parts.append(grant['identifier'])
                if (grant['funding_body']): grant_parts.append(f'Funding Body: {grant['funding_body']['name']}')
                if (grant_parts): grants.append(', '.join(grant_parts))
            if (grants): information.append(f'**Grants:**\n- {'\n- '.join(grants)}')
        information.append(f'**ID:** {response['id']}')
        information.append(f'**Identifier:** {response['identifier']}')
        if (response['media']): information.append(f'**Media:** {response['media']}')
        if (response['metadata_source']): information.append(f'**Metadata Source:** {response['metadata_source']}')
        if (response['operator']):
            if (response['operator']['name']): information.append(f'**Operator:** {response['operator']['name']}')
        if (response['orthographic_notes']): information.append(f'**Orthographic Notes:** {response['orthographic_notes']}')
        information.append(f'**Permalink:** {response['permalink']}')
        if (response['region']): information.append(f'**Region:** {response['region']}')
        if (response['subject_languages']):
            languages = []
            for language in response['subject_languages']:
                if (language['retired']): languages.append(f'{language['name']} (Retired)')
                else: languages.append(language['name'])
            if (languages): information.append(f'**Subject Languages:**\n- {'\n- '.join(languages)}')
        if (response['tape_location'] != None): information.append(f'**Tape Location:** {response['tape_location']}')
        information.append(f'**Title:** {response['title']}')
        if (response['university']): information.append(f'**University:** {response['university']['name']}')

        st.subheader('Collection Metadata')
        for info in information:
            if (isinstance(info, dict)):
                with st.expander('**DOI JSON:**'): st.json(info)
            else: st.write(info)

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
                        }
                    }
                }
            '''
            variables = {'limit': st.session_state.PAGE_LIMIT, 'page': (page + 1), 'full_identifier': st.session_state.collection}
            response = st.session_state.session.post(
                st.session_state.API_URL,
                json = {'query': query, 'variables': variables}
            ).json()['data']['items']
            collection_items.extend(response['results'])
            time.sleep(0.2)

        st.subheader('Items in Collection')
        for item in collection_items: st.write(f'- {item['full_identifier']}')