# Melbourne_Jewish_Museum_Concert_Archive
Program for accessing concert information. Main code is stored in Jewish_Concert_Archive.ipynb. Information extracted (via OCR using Claude) from the Dunera Dataset (Melbourne Jewish Museum) is stored in jewish_concert_archive.json. Outputs from the program are stored as locations.png and performance_network.html.


The jewish_concert_archive.json file was obtained by feeding the Dunera Data Set (a collection of wartime concert program scans and photographs, found here: https://drive.google.com/drive/u/1/folders/1hDcqcQJMfwFI4Jilg3F7tddzn1SUabeq) to Claude Co-Work, and prompting it to use the information contained within the scans to create a JSON file of the following layout:
-archive overview
-concerts
  -title
  -alternate titles
  -type
  -venue
  -location
  -date
  -presented_by
  -overall_credits
  -acts
    -act_name
    -songs
      -number
      -title
      -type
      -credits
      -composer
      -lyrics
      -performers
      -arranger
      -based_on_tune
      -additional_notes
Claude was able (with some additional prompting) to extract and intepret the text contained within the program scans to create the JSON file.
