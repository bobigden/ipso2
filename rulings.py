import csv
import datetime
import glob
import json
import re
import urllib3
from bs4 import BeautifulSoup

pathh = "D:/programming/separate_python/trans_media_watch/"

#%% Get all rulings
url = "https://www.ipso.co.uk/rulings-and-resolution-statements/?page=1&perPage=20000"

http = urllib3.PoolManager()
main_response = http.request('GET', url)
bytes = main_response.data
soup = BeautifulSoup(bytes, 'html.parser')

#%% Process all rulings
tops = soup.find_all("div", class_ = "rulings-content")
assert len(tops) == 1
links = tops[0].find_all("a")

data = []
for i, link in enumerate(links):
    cells = link.find_all("div", class_ = "tabs--table-cell")
    dat = {"url": link["href"]}
    for typ, cell, lst in zip(["title", "provisions", "outcome"], cells[:3], [False, True, False]):
        arr = [x.strip() for x in cell.text.split("\n")[2:]]
        arr = [x for x in arr if x != ""]
        if lst:
            dat[typ] = arr
        else:
            if typ == "title" and len(arr) == 0:
                break
            dat[typ] = arr[0]
    if "title" in dat:
        data.append(dat)

#%% Save all rulings
with open(pathh + 'ipso/ipso_list.csv', "w", encoding = "utf-8", newline = '') as csvfile:
    writer = csv.writer(csvfile)  #, delimiter = ',', quotechar = '"', quoting = csv.QUOTE_MINIMAL)
    for row in data:
        writer.writerow(row.values())


#%% Get Specifics - functions

def save_json(path, data):
    with open(path, 'w', encoding = 'utf-8') as f:
        json.dump(data, f, ensure_ascii = False, indent = 4, default = str)


def load_json(path):
    with open(path, encoding = 'utf-8') as data_file:
        return json.load(data_file)

# finds date of the format dd/mm/yy(yy)
# date must be preceded by some text
def find_nice_date(elem, pre_text):
    arrs = re.findall(f"{pre_text}\s*(\d+[/\s]\d+[/\s]\d+)", elem, re.IGNORECASE)
    arrs = list(set(arrs))
    if len(arrs) != 1:
        return None
    arr = arrs[0]
    arr = arr.replace(" ", "/")
    while "//" in arr:
        arr = arr.replace("//", "/")
    if len(arr.split("/")) != 3:
        return None
    last_len = len(arr.split("/")[-1])
    year_type = "y" if last_len == 2 else "Y"
    if arr == '180/2/2021':
        return datetime.datetime(2021, 2, 18)  # special case typo
    if arr == '270/2/2018':
        return datetime.datetime(2018, 2, 27)  # special case typo
    if arr == '21/016/2016':
        return datetime.datetime(2016, 6, 21)  # special case typo
    return datetime.datetime.strptime(arr, f"%d/%m/%{year_type}")


def find_date(elem, pre_text):
    elem = elem.replace("//", "/")
    nice = find_nice_date(elem, pre_text)
    if nice is not None:
        return True, nice
    
    arrs = re.findall(f"{pre_text}\s+([^\s]+) ([^\s]+) (\d+)", elem, re.IGNORECASE)
    if len(arrs) != 1:
        return False, arrs
    
    arr = list(arrs[0])
    
    if arr[1][0].isnumeric() and not arr[0][0].isnumeric():
        tmp = arr[0]
        arr[0] = arr[1]
        arr[1] = tmp
    
    # if len(arr[2][-1]) > 4:
    #     arr[2] = arr[2][:4]
    if len(arr[0]) > 2:
        if arr[0][-2:] in ["rd", "th", "st", "nd"]:
            arr[0] = arr[0][:-2]
        else:
            raise Exception(f"Strange date {arr}")
    return True, datetime.datetime.strptime(" ".join(arr), "%d %B %Y")


# Get first paragraph, usually it starts with "1.", Usually is after 'summary of complaint'
# First paragraph contains the date of the complaint
def get_first_paragraph(mainn):
    ps = [x.text.replace("\n", " ") for x in mainn.find_all("p")]
    if len(ps) <= 1:
        print("Page does not use <p>")
        return None
    
    # Get index of 'summary of complaint' heading
    summary_ind = None
    summary_inds = [i for i, p in enumerate(ps) if 'summary of complaint' in p.lower() and len(p) < 30]
    if len(summary_inds) == 1:
        summary_ind = summary_inds[0]
        summary_reliable = True
    else:
        summary_reliable = False
        for i in range(5):
            tmp = ps[i].strip()
            if tmp[:2] == "1.":
                print("WARNING DID NOT FIND 'Summary of Complaint'")
                summary_ind = i - 1
    if summary_ind is None:
        return None
    
    # First paragraph is usually directly after 'summary of complaint' but somethimes there is whitespace. Find with "1."
    first_paragraph = None
    found_numbering = False
    first_ind = summary_ind + 1
    for i in range(3):
        tmp = ps[summary_ind + 1 + i].strip()
        if tmp[:2] == "1.":
            found_numbering = True
            first_paragraph = tmp
            first_ind = summary_ind + 1 + i
            break
    
    if first_paragraph is None:
        if summary_reliable:
            first_paragraph = ps[summary_ind + 1]
        else:
            raise Exception("Cannot find first paragraph")
    
    # Sometimes the first paragraph contains newlines
    if found_numbering:
        for i in range(5):
            tmp = ps[first_ind + 1 + i]
            if tmp[:2] == "2.":
                break
            else:
                first_paragraph += " " + tmp
    
    return first_paragraph


# Main function to update the data from the scraped ruling page
def update_dat(dat, soup2):
    # Find publication source
    d1s = soup2.find_all("div", class_ = "column--third article--author")
    assert len(d1s) == 1
    arr = d1s[0].text.split("\n")
    pub_ind = arr.index("Publication")
    #assert pub_ind in [5, 7]
    dat["publication"] = arr[pub_ind + 1]
    
    # Get the main block of text
    top_div = soup2.find("div", {"id": "row--content"})
    mains = top_div.find_all("div", class_ = "container")
    assert len(mains) == 2
    mainn = mains[1]
    #text_alt = "\n".join([x.text for x in mainn.find_all("p")])
    main_text = mainn.text
    reg_text = main_text.replace("\n", " ")
    
    # Get publication date from first paragraph, look for "published ... on"
    # Do not store imprecise dates which only give the month
    first_paragraph = get_first_paragraph(mainn)
    if first_paragraph is not None:
        suc = True
        if "published on 17 and 18 August 2015" in first_paragraph:
            tmp = datetime.datetime(2015, 8, 17)
        elif "published on www.getwestlondon.co.uk on 10 October 2014" in first_paragraph:
            tmp = datetime.datetime(2014, 10, 10)
        elif "published on 23 Mach 2018" in first_paragraph:
            tmp = datetime.datetime(2018, 3, 23)
        else:
            suc, tmp = find_date(first_paragraph, "published (?:in print )?(?:online )?on")
    else:
        suc = False
        tmp = []
    if suc:
        dat["published_on"] = tmp
    else:
        if len(tmp) > 1:
            print("MULTIPLE PUBLICATION DATES")
        elif len(tmp) == 0 and "published in" in mainn:
            print("INNACURATE PUBLICATION DATE")
    
    # Check to see whether date recieved and concluded should exist
    contains_relevant_word_for_date = False
    for k in ["recieved", "concluded", "issued"]:
        if k in reg_text[:300]:
            contains_relevant_word_for_date = True
    
    # Get dates recieved and concluded.
    # Wording varies substancially and contains typos
    for k, k2 in [
        ("received", "(?:complaints? )?(?:received|made)(?: by IPSO)?"),
        ("concluded", "(?:complaints? |decisi?on )?(?:concluded|issued|completed)(?: by IS?PS?O)?(?: to the parties)?")]:
        suc, tmp = find_date(reg_text, f"Datd?e {k2}[:.]?")
        if suc:
            dat[f"{k}_on"] = tmp
        elif contains_relevant_word_for_date:
            raise Exception(f"Cannot find: date {k}:  {tmp}")
    
    if "concluded_on" in dat and "received_on" in dat:
        dat["complaint_processing_days"] = (dat["concluded_on"] - dat["received_on"]).days
    
    # Store the outcome of the process
    med_re = re.findall("Mediated outcome(.*)Date complaint received", reg_text, re.IGNORECASE)
    if len(med_re) > 0:
        dat["mediated_outcome"] = med_re[0].strip()
    
    end_re = re.findall("Conclusion(?:\(s\))?s?(.*)Remedial Action Required(.*)Date", reg_text, re.IGNORECASE)
    if len(end_re) > 0:
        dat["conclusion_long"] = end_re[0][0].strip()
        dat["remedial_action"] = end_re[0][1].strip()
    
    if not (len(med_re) > 0) ^ (len(end_re) > 0):
        print("MISSING CONCLUSION OR MEDIATION")
    
    dat["text"] = main_text


#%% Get specific data for all scraped resolutions, save as json
for dat in data:
    bad = False
    for k in []:  #"03743-18", "03195-18", "03194-18"]:
        if k in dat["url"]:
            bad = True
            break
    if bad:
        continue
    
    out_name = pathh + "ipso/data/" + dat["title"].replace(" ", "_").replace("/", "_") + ".json"
    if len(glob.glob(out_name)) > 0:
        print(f"Already got {dat['title']}, skipping")
        continue
    
    try:
        url2 = "https://www.ipso.co.uk" + dat["url"]
        print(dat["title"], url2)
        http = urllib3.PoolManager()
        main_response = http.request('GET', url2)
        bytes = main_response.data
        soup2 = BeautifulSoup(bytes, 'html.parser')
        update_dat(dat, soup2)
        
        save_json(out_name, dat)
    except  Exception as e:
        print("ERROR! ", e)
        pass

#%%
