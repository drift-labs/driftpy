#%%
from gazpacho import get, Soup
from bs4 import BeautifulSoup

url = 'https://github.com/drift-labs/protocol-v2/releases'
html = get(url)
soup = BeautifulSoup(html, 'html.parser')
divs = soup.find_all("div", class_="clearfix container-xl px-3 px-md-4 px-lg-5 mt-4")

#%%
div = divs[0]
div = list(div.children)[5]

#%%
info = div.find('section')
program_id = info.find('h2').text
commit = info.find_all("code")[0].text

print(program_id, commit)

#%%
## update config program_id 
with open("src/driftpy/constants/config.py", 'r') as f: 
    data = f.read()

import re 
result = re.search("clearing_house_program_id=PublicKey\(\'(.*)\'\)", data)
old_id = result.group(1)
data = data.replace(old_id, program_id)

with open("src/driftpy/constants/config.py", 'w') as f: 
    f.write(data)

#%%
# update protocol commit
from subprocess import Popen

Popen(
    'git fetch --all'.split(' '), 
    cwd='protocol-v2/'
).wait()

#%%
Popen(
    f'git checkout {commit}'.split(' '), 
    cwd='protocol-v2/'
).wait()

#%%
Popen(
    'bash update_idl.sh'.split(' '), 
).wait()

print('done! :)')
