import json
import streamlit as st

if (st.session_state.logged_in == False): st.header('Login First!')
else:
    # Gets desired item from user
    st.header('View Item Metadata')
    st.selectbox('Item Full Identifier:', st.session_state.item_identifiers_list, None, key = 'item', placeholder = 'Select Item Full Identifier', persist_state = 'session')

    if (st.session_state.item != None):
        # Retrieves item metadata
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
                        identifier
                    }
                    collector {
                        name
                    }
                    content_languages {
                        name
                        retired
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
                    doi_json
                    essences {
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
                        retired
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
        ).json()['data']['item']

        # Cleans and formats metadata
        information = []
        if (response['access_class']): information.append(f'**Access Class:** {response['access_class']}')
        if (response['access_condition_name']): information.append(f'**Access Condition:** {response['access_condition_name']}')
        if (response['access_narrative']): information.append(f'**Access Narrative:** {response['access_narrative']}')
        if (response['born_digital'] != None): information.append(f'**Born Digital:** {response['born_digital']}')
        if (response['boundaries']):information.append(f'**Boundary:**\n- *East Limit:* {response['boundaries']['east_limit']}\n- *North Limit:* {response['boundaries']['north_limit']}\n- *South Limit:* {response['boundaries']['south_limit']}\n- *West Limit:* {response['boundaries']['west_limit']}')
        if (response['citation']): information.append(f'**Citation:** {response['citation']}')
        information.append(f'**Collection:** {response['collection']['identifier']}')
        if (response['collector']['name']): information.append(f'**Collector:** {response['collector']['name']}')
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
        if (response['created_at']): information.append(f'**Created At:** {response['created_at']}')
        if (response['data_categories']):
            categories = []
            for category in response['data_categories']: categories.append(category['name'])
            if (categories): information.append(f'**Data Categories:**\n- {'\n- '.join(categories)}')
        if (response['data_types']):
            types = []
            for type in response['data_types']: types.append(type['name'])
            if (types): information.append(f'**Data Types:**\n- {'\n- '.join(types)}')
        if (response['description']): information.append(f'**Description:** {response['description']}')
        if (response['dialect']): information.append(f'**Dialect:** {response['dialect']}')
        if (response['digitised_on']): information.append(f'**Digitised On:** {response['digitised_on']}')
        if (response['discourse_type']): information.append(f'**Discourse Type:** {response['discourse_type']['name']}')
        if (response['doi']): information.append(f'**DOI:** {response['doi']}')
        if (response['doi_json']): information.append(json.loads(response['doi_json']))
        if (response['essences_count']): information.append(f'**Essences Count:** {response['essences_count']}')
        information.append(f'**Full Identifier:** {response['full_identifier']}')
        information.append(f'**ID:** {response['id']}')
        information.append(f'**Identifier:** {response['identifier']}')
        if (response['ingest_notes']): information.append(f'**Ingest Notes:** {response['ingest_notes']}')
        if (response['item_agents']):
            agents = []
            for agent in response['item_agents']:
                if (agent['role_name'] and agent['user_name']): agents.append(f'*{agent['role_name']}:* {agent['user_name']}')
            if (agents): information.append(f'**Item Agents:**\n- {'\n- '.join(agents)}')
        if (response['language']): information.append(f'**Language:** {response['language']}')
        information.append(f'**Metadata Exportable:** {response['metadata_exportable']}')
        if (response['operator']):
            if (response['operator']['name']): information.append(f'**Operator:** {response['operator']['name']}')
        if (response['original_media']): information.append(f'**Original Media:** {response['original_media']}')
        if (response['originated_on']): information.append(f'**Originated On:** {response['originated_on']}')
        if (response['originated_on_narrative']): information.append(f'**Originated On Narrative:** {response['originated_on_narrative']}')
        information.append(f'**Permalink:** {response['permalink']}')
        if (response['private'] != None): information.append(f'**Private:** {response['private']}')
        if (response['public'] != None): information.append(f'**Public:** {response['public']}')
        if (response['received_on']): information.append(f'**Received On:** {response['received_on']}')
        if (response['region']): information.append(f'**Region:** {response['region']}')
        if (response['subject_languages']):
            languages = []
            for language in response['subject_languages']:
                if (language['retired']): languages.append(f'{language['name']} (Retired)')
                else: languages.append(language['name'])
            if (languages): information.append(f'**Subject Languages:**\n- {'\n- '.join(languages)}')
        if (response['title']): information.append(f'**Title:** {response['title']}')
        if (response['tracking']): information.append(f'**Tracking:** {response['tracking']}')
        if (response['university']): information.append(f'**University:** {response['university']['name']}')
        if (response['updated_at']): information.append(f'**Updated At:** {response['updated_at']}')

        st.subheader('Item Metadata')
        for info in information:
            if (isinstance(info, dict)):
                with st.expander('**DOI JSON:**'): st.json(info)
            else: st.write(info)

        st.subheader('Essences')
        for essence in response['essences']:
            if essence['permalink']: st.write(f'- {essence['permalink']}')
            else: st.write('- Permalink Missing')