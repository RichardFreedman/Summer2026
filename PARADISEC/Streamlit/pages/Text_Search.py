from bs4 import BeautifulSoup
import chardet
from charset_normalizer import from_bytes
import codecs
from fuzzysearch import find_near_matches
import io
import math
import mimetypes
import pandas as pd
import pymupdf
from pylatexenc.latex2text import LatexNodes2Text
import srt
import streamlit as st
from striprtf.striprtf import rtf_to_text
import time
from urllib.parse import quote
import xml.etree.ElementTree as et
import zipfile

if (st.session_state.get('use_dev', False)): st.switch_page('pages/Text_Search_dev.py')

if (st.session_state.logged_in == False): st.header('Login First!')
else:
    st.header('Filters')

    # Required language filter
    st.selectbox('Language:', st.session_state.languages_list, None, key = 'filter_language', placeholder = 'Select Language (Required)', persist_state = 'session')

    # Additional optional filters
    st.selectbox('Collection ID:', st.session_state.collection_identifiers_list, None, key = 'filter_collection', placeholder = 'Select Collection Identifier (Optional)', persist_state = 'session')
    # BUG Filtering by collector_name has no effect
    # st.selectbox("Collector's Name:", st.session_state.collectors_list, None, key = 'filter_collector', placeholder = "Select Collector's Name (Optional)", persist_state = 'session')
    st.selectbox('Region:', st.session_state.regions_list, None, key = 'filter_region', placeholder = 'Select Region (Optional)', persist_state = 'session')
    # BUG Filtering by university_name has no effect
    # st.selectbox('University Name:', st.session_state.universities_list, None, key = 'filter_university', placeholder = 'Select University Name (Optional)', persist_state = 'session')



    # Search parameters
    st.header('Search Parameters')

    st.segmented_control('Search Type:', ['Exact', 'Fuzzy'], key = 'search_type', persist_state = 'session')
    st.text_area('Search Text:', height = 'content', key = 'search_text', persist_state = 'session')

    if (st.session_state.filter_language != None and st.session_state.search_type != None and st.session_state.search_text != ""):
        if st.button('Search', icon = ':material/search:'):
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
            pages = math.ceil(total_filtered_items / st.session_state.PAGE_LIMIT)

            filtered_essences = {}
            total_essence_files = 0
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
                    essences_info = {}
                    for essence in result['essences']:
                        essences_info.update({essence['permalink']: essence['mimetype']})
                        total_essence_files = total_essence_files + 1
                    filtered_essences.update({result['full_identifier']: essences_info})
                time.sleep(0.2)



            # Removes all essences/items that don't have actual text or are purely descriptive/metadata
            searchable_mimetypes = [
                'application/eaf+xml',
                'application/flextext+xml',
                'application/pdf',
                'application/vnd.oasis.opendocument.spreadsheet',
                'application/vnd.oasis.opendocument.text',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/xml',
                'application/x-subrip',
                'application/zip',
                'text/csv',
                'text/html',
                'text/plain',
                'text/rtf',
                'text/xml',
                'text/x-tex'
            ]
            unsearchable_items = []
            for item_identifier, essences_info in filtered_essences.items():
                unsearchable_essences = [permalink for permalink, mimetype in essences_info.items() if mimetype not in searchable_mimetypes]
                for essence in unsearchable_essences:
                    del essences_info[essence]
                    total_essence_files = total_essence_files - 1
                if (len(essences_info) == 0): unsearchable_items.append(item_identifier)
            for item in unsearchable_items: del filtered_essences[item]

            if (total_essence_files == 0): st.subheader('No searchable files under these parameters!')
            else:
                retrieval_progress_bar = st.progress(0.0, 'Retrieving Files...')
                file_percent = 1.0 / total_essence_files
                completion_percent = 0.0

                essence_bytes = {}
                forbidden_permalinks = []
                for essences_info in filtered_essences.values():
                    for permalink in essences_info.keys():
                        # Retrieves the bytes from the raw file given the catalog permalink
                        filename = permalink.rsplit('/', 1)[-1]
                        encoded_permalink = quote(permalink, safe='')
                        essence_file_url = f'https://admin-catalog.paradisec.org.au/api/v1/oni/file/{encoded_permalink}'
                        st.session_state.raw_session.params.update({'filename': filename})
                        raw_response = st.session_state.raw_session.get(essence_file_url)

                        # Checks if a file is actually accessible
                        if ('{"error":{"code":"FORBIDDEN","message":"You do not have permission to access this resource"' in raw_response.text): forbidden_permalinks.append(permalink)
                        else: essence_bytes.update({permalink: raw_response.content})

                        completion_percent = completion_percent + file_percent
                        retrieval_progress_bar.progress(completion_percent, 'Retrieving Files...')
                        time.sleep(0.2)

                retrieval_progress_bar.progress(1.0, 'Files Retrieved!')

                # Removes files without open access
                forbidden_items = []
                for item_identifier, essences_info in filtered_essences.items():
                    forbidden_essences = [permalink for permalink in essences_info if permalink in forbidden_permalinks]
                    for essence in forbidden_essences:
                        del essences_info[essence]
                        total_essence_files = total_essence_files - 1
                    if (len(essences_info) == 0): forbidden_items.append(item_identifier)
                for item in forbidden_items: del filtered_essences[item]

                # Chooses the best decoding option if available or utf-8 and replaces errors
                def safe_decode(encoded_string: bytes) -> str:
                    try: return encoded_string.decode('utf-8')
                    except UnicodeDecodeError:
                        det_guess = chardet.detect(encoded_string)
                        set_guess = from_bytes(encoded_string).best()

                        det_encoding = codecs.lookup(det_guess['encoding']).name
                        set_encoding = codecs.lookup(set_guess.encoding).name

                        if (det_encoding == set_encoding or det_guess['confidence'] > 0.1): encoding = det_encoding
                        else: encoding = 'utf-8'

                        return encoded_string.decode(encoding, 'replace')

                # Turns raw file bytes into a string with the contained meaningful text
                def parse_essence(raw_string: bytes, mimetype: str) -> str:
                    try:
                        match mimetype:
                            case 'application/eaf+xml':
                                xml = et.fromstring(raw_string)
                                annotations = [annotation.text.strip() for annotation in xml.findall('.//ANNOTATION_VALUE') if annotation.text and annotation.text.strip()]
                                return ' '.join(annotations)
                            case 'application/flextext+xml':
                                xml = et.fromstring(raw_string)
                                all_text = []
                                for phrase in xml.findall('.//phrase'):
                                    words = phrase.find('words')
                                    if (words != None):
                                        text_words = []
                                        for word in words.findall('word'):
                                            text_item = word.find("item[@type='txt']")
                                            if (text_item != None and text_item.text): text_words.append(text_item.text.strip())
                                            else:
                                                punctuation_item = word.find("item[@type='punct']")
                                                if (punctuation_item != None and punctuation_item.text): text_words.append(punctuation_item.text.strip())
                                        original_text = ' '.join(text_words)
                                    else:
                                        text_item = phrase.find("item[@type='txt']")
                                        original_text = text_item.text.strip() if text_item != None and text_item.text else ''

                                    gloss_items = phrase.findall("item[@type='gls']")
                                    translation_texts = ' '.join(gloss.text.strip() for gloss in gloss_items if gloss.text and gloss.text.strip())

                                    combined_text = f'{original_text} {translation_texts}'.strip()
                                    if (combined_text): all_text.append(combined_text)
                                return ' '.join(all_text)
                            case 'application/pdf':
                                pdf = pymupdf.open(stream = raw_string, filetype = 'pdf')
                                pages_text = [page.get_text() for page in pdf]
                                pdf.close()
                                return '\n'.join(text.strip() for text in pages_text if text.strip())
                            case 'application/vnd.oasis.opendocument.spreadsheet' | 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet':
                                engine = 'odf' if mimetype.endswith('opendocument.spreadsheet') else 'openpyxl'
                                sheets = pd.read_excel(io.BytesIO(raw_string), sheet_name = None, engine = engine)
                                return '\n'.join(df.dropna(axis=1, how='all').to_string(index=False) for df in sheets.values())
                            case 'application/vnd.oasis.opendocument.text':
                                # NOTE Can't find files to test with - may only be those without open access
                                namespace = '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}'
                                with zipfile.ZipFile(io.BytesIO(raw_string)) as zip: xml_bytes = zip.read('content.xml')
                                xml = et.fromstring(xml_bytes)
                                paragraphs = []
                                for paragraph in xml.iter(f'{namespace}p'):
                                    parts = []
                                    for element in paragraph.iter():
                                        if (element.text): parts.append(element.text)
                                        if (element.tag == f'{namespace}line-break'): parts.append('\n')
                                        elif (element.tag == f'{namespace}tab'): parts.append('\t')
                                        elif (element.tag == f'{namespace}s'): parts.append(' ' * int(element.get(f'{namespace}c', '1')))
                                        if (element.tail): parts.append(element.tail)
                                    paragraphs.append(''.join(parts))
                                return '\n'.join(text.strip() for text in paragraphs if text.strip())
                            case 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                                namespace = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
                                with zipfile.ZipFile(io.BytesIO(raw_string)) as zip: xml_bytes = zip.read('word/document.xml')
                                xml = et.fromstring(xml_bytes)
                                paragraphs = []
                                for paragraph in xml.iter(f'{namespace}p'):
                                    parts = []
                                    for element in paragraph.iter():
                                        if (element.tag == f'{namespace}t' and element.text): parts.append(element.text)
                                        elif (element.tag in (f'{namespace}br', f'{namespace}cr')): parts.append('\n')
                                        elif (element.tag == f'{namespace}tab'): parts.append('\t')
                                    paragraphs.append(''.join(parts))
                                return '\n'.join(text.strip() for text in paragraphs if text.strip())
                            case 'application/xml' | 'text/xml':
                                xml = et.fromstring(raw_string)
                                fragments = [text.strip() for text in xml.itertext() if text.strip()]
                                return ' '.join(fragments)
                            case 'application/x-subrip':
                                decoded_string = safe_decode(raw_string)
                                subtitles = list(srt.parse(decoded_string))
                                return ' '.join(subtitle.content.replace('\n', ' ') for subtitle in subtitles)
                            case 'application/zip':
                                texts = []
                                with zipfile.ZipFile(io.BytesIO(raw_string)) as zip:
                                    for name in zip.namelist():
                                        if (name.endswith('/')): continue
                                        file_mimetype, _ = mimetypes.guess_type(name)
                                        if (file_mimetype not in searchable_mimetypes): continue
                                        try:
                                            file_bytes = zip.read(name)
                                            file_text = parse_essence(file_bytes, file_mimetype)
                                            if (file_text): texts.append(f'{name}\n\n{file_text}')
                                        except Exception: texts.append(f'{name}\n\nFile Parsing Error')
                                return '\n\n\n\n'.join(texts)
                            case 'text/csv' | 'text/plain': return safe_decode(raw_string)
                            case 'text/html':
                                soup = BeautifulSoup(raw_string, 'html.parser')
                                return soup.get_text(' ', True)
                            case 'text/rtf':
                                decoded_string = raw_string.decode('latin-1')
                                return rtf_to_text(decoded_string)
                            case 'text/x-tex':
                                decoded_string = safe_decode(raw_string)
                                return LatexNodes2Text().latex_to_text(decoded_string)
                    except Exception: return 'File Parsing Error'

                # Gets the text from all the retrieved files
                essence_text = {}
                for essences_info in filtered_essences.values():
                    for permalink, mimetype in essences_info.items():
                        raw_string = essence_bytes[permalink]
                        plain_string = parse_essence(raw_string, mimetype)
                        essence_text.update({permalink: plain_string})

                # Checks the search text against the text of every file depending on search type
                if (st.session_state.search_type == 'Exact'): matches = [permalink for permalink, text in essence_text.items() if st.session_state.search_text in text]
                else: matches = [permalink for permalink, text in essence_text.items() if find_near_matches(st.session_state.search_text, text, max_l_dist = max(1, int(len(st.session_state.search_text) * 0.15)))]

                st.header('Search Results')
                if (not matches): st.write('No files matched your search!')
                else:
                    # Gets the items that matched the search and how many matches each item had, as well as pairs item identifier and related permalinks
                    matched_items = {}
                    matched_permalinks = {}
                    for permalink in matches:
                        for item_identifier, essences_info in filtered_essences.items():
                            if (permalink in essences_info):
                                count = matched_items.get(item_identifier, 0) + 1
                                matched_items.update({item_identifier: count})
                                matched_permalinks.update({permalink: item_identifier})
                                break

                    # Orders matched items so those with more files that matched appear first
                    ordered_matched_items = sorted(matched_items, key = matched_items.get, reverse = True)

                    # Displays the key information for all items that matched
                    query = '''
                        query($fullIdentifier: ID!) {
                            item(fullIdentifier: $fullIdentifier) {
                                title
                                description
                            }
                        }
                    '''
                    for item_identifier in ordered_matched_items:
                        variables = {'fullIdentifier': item_identifier}
                        response = st.session_state.session.post(
                            st.session_state.API_URL,
                            json = {'query': query, 'variables': variables}
                        )

                        st.write('---')
                        st.write(f'Title: {response.json()['data']['item']['title']}')
                        st.write(f'Description: {response.json()['data']['item']['description']}')
                        st.write(f'Identifier: {item_identifier}')
                        item_permalinks = [permalink for permalink, identifier in matched_permalinks.items() if identifier == item_identifier]
                        st.write(f'Link(s) to matched essence(s): {' | '.join(item_permalinks)}')

                        time.sleep(0.2)