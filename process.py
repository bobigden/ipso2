import pandas as pd
import glob
import matplotlib as mpl
import matplotlib.pyplot as plt

from storage import load_json


#pd.set_option('display.max_columns', 500)
#pd.set_option('display.width', 250)
#pd.set_option('display.max_rows', 5000)
#%%
def format_text(txt):
    while "\n\n" in txt:
        txt = txt.replace("\n\n", "\n")
    txt = txt.replace("\n", "    ")
    txt = txt.replace("\t", "  ")
    txt.replace("|", ",")
    return txt


def count_keywords(dat):
    txt = dat["text"]
    occurances = 0
    for word in ["transgender", "transex", "intersex", "non-binary"]:
        occurances += txt.count(word)
    dat["keyword_occurances"] = occurances
    dat["trans_occurances"] = txt.count("trans")


#%%
rows = []
for f in glob.glob("ipso/data/*.json"):
    dat = load_json(f)
    for k in ["text", "remedial_action", "conclusion_long", "mediated_outcome"]:
        if k in dat:
            dat[k] = format_text(dat[k])
    dat["url"] = "https://www.ipso.co.uk" + dat["url"]
    count_keywords(dat)
    rows.append(dat)

#%%
df = pd.DataFrame(rows)
df.sort_values("keyword_occurances", inplace = True, ascending = False)
for k in ["received_on", "published_on", "concluded_on"]:
    df[k] = pd.to_datetime(df[k])

#%%
df.to_csv("ipso/ipso_long.csv", sep = "|")
df.to_csv("ipso/ipso_tab.csv", sep = "\t")

#%%
df2 = df
df2 = df2[~df2.received_on.isnull()]
df2 = df2[~df2.complaint_processing_days.isnull()]
df2 = df2[df2.complaint_processing_days > 1]

received_dates = df
plt.plot(df2.received_on, df2.complaint_processing_days, 'x', alpha = 0.3)

#%%
