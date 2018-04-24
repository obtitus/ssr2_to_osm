import os
import re
from datetime import datetime
import logging
logger = logging.getLogger('utility_to_osm.ssr2.generate_webpage')

import utility_to_osm.argparse_util as argparse_util
from utility_to_osm.kommunenummer import kommunenummer, kommune_fylke
import utility_to_osm.file_util as file_util
from utility_to_osm.file_util import open_utf8
from utility_to_osm import osmapis

from jinja2 import Template
import humanize

link_template = u'<a href="{href}" title="{title}">{text}</a>'


footer = """
<!-- FOOTER  -->
<div id="footer_wrap" class="outer">
  <footer class="inner">
    <p class="copyright">
      This page is maintained by <a href="https://github.com/obtitus">obtitus</a>
    </p>
    <p class="copyright">
      OSM data &copy;<a href="http://openstreetmap.org">OpenStreetMap</a> contributors,
      all osm data licensed under
      <a href=https://opendatacommons.org/licenses/odbl/>ODbL</a>
    </p>
    <p class="copyright">
      All place data extracted from SSR &copy;<a href="https://kartverket.no">kartverket.no</a> under 
      <a href="https://creativecommons.org/licenses/by/3.0/no/">CC BY 3.0</a>
    </p>
</footer>
</div>
"""

header = """
<!-- HEADER -->
<div id="header_wrap" class="outer">
  <header class="inner">
    <a id="forkme_banner" href="https://github.com/obtitus/ssr2_to_osm">View on GitHub</a>
    <h1 id="project_title">SSR2 import to OpenStreetMap.org</h1>
    <h2 id="project_tagline">Data files for importing Norwegian placenames from Kartverket, ssr2, into OpenStreetMap</h2>
  </header>
</div>
"""

info = """
The table below contains: 
<ol>
<li> A "Dataset for import" file containing all of the data, including some additional
raw SSR tags for filtering and debugging that should not be uploaded to OSM. </li>
<li> A "Excerpts for import" containing subsets of the data, ready for import.</li>
<li> A "Excluded from import" column with any data that is either missing a 
<a href=https://wiki.openstreetmap.org/wiki/Key:name>name=*</a>
tag (but typically contains either 
<a href=https://wiki.openstreetmap.org/wiki/Key:old_name>old_name=*</a> or
<a href=https://wiki.openstreetmap.org/wiki/Key:loc_name>loc_name=*</a>).
The column also contain data that lacks a translation from SSR to OSM tags (see <a href=https://drive.google.com/open?id=1krf8NESSyyObpcV8TPUHInUCYiepZ6-m>tagging table</a>), typically excluded since these
are coved by seperate imports. 
Data from this column should in general not be imported.</li>
<li> Raw data from Kartverket (SSR) in the rightmost column. </li>
</ol>
See the <a href=http://wiki.openstreetmap.org/wiki/No:Import_av_stedsnavn_fra_SSR2>import wiki</a> for further details.
"""

def create_text(filename, f):
    if f.endswith('.osm'):
        if re.match('\d\d\d\d-', f):
            f = f[5:]
            f = f.replace('-', ' ')
            f = f.replace('tagged', '')
            f = f.replace(' .osm', '.osm')
            f = f.strip()
            if f == '.osm':
                f = 'all.osm'

        if 'clean' in filename:
            f = 'clean-' + f

        content = file_util.read_file(filename)
        osm = []#osmapis.OSM.from_xml(content)
        N_nodes = len(osm)
        N_nodes_str = '%s node' % N_nodes
        if N_nodes > 1:
            N_nodes_str += 's'

        # N_bytes = os.path.getsize(filename)
        # N_bytes_str = humanize.naturalsize(N_bytes, format='%d')

        f = '%s (%s)' % (f, N_nodes_str)
    else:
        pass
    return f

def write_template(template_input, template_output, **template_kwargs):
    with open_utf8(template_input) as f:
        template = Template(f.read())

    template_kwargs['header'] = template_kwargs.pop('header', header)
    template_kwargs['footer'] = template_kwargs.pop('footer', footer)
    page = template.render(**template_kwargs)

    with open_utf8(template_output, 'w') as output:
        output.write(page)

def create_main_table(data_dir='output', cache_dir='data'):
    table = list()
    last_update = ''
    kommune_nr2name, kommune_name2nr = kommunenummer(cache_dir=cache_dir)
    kommuneNr_2_fylke = kommune_fylke(cache_dir=cache_dir)
    fylker = list()
    
    for kommune_nr in os.listdir(data_dir):
        folder = os.path.join(data_dir, kommune_nr)
        if os.path.isdir(folder):
            try:
                kommune_name = kommune_nr2name[int(kommune_nr)] + ' kommune'
            except KeyError as e:
                logger.warning('Could not translate kommune_nr = %s to a name. Skipping', kommune_nr)
                #kommune_name = 'ukjent'
                continue
            except ValueError as e:
                if kommune_nr == 'ZZ':
                    kommune_name = 'Outside mainland'
                else:
                    raise ValueError(e)

            try:
                fylke_name, fylke_nr = kommuneNr_2_fylke[int(kommune_nr)]
                t = (fylke_name, fylke_nr)
                if t not in fylker:
                    fylker.append(t)
                
                fylke_name += ' fylke'                    
                
            except KeyError as e:
                logger.warning('Could not translate kommune_nr = %s to a fylke-name. Skipping', kommune_nr)
                #fylke_name = 'ukjent'
                continue
            except ValueError:
                if kommune_nr == 'ZZ':
                    fylke_name = ''
                else:
                    raise ValueError(e)
            

            row = list()
            dataset_for_import = [] # expecting a single entry here
            excluded_from_import = []
            excerpts_for_import = []
            raw_data = []
            log = []
            for root, dirs, files in os.walk(folder):
                for f in files:
                    f = f.decode('utf8')
                    if f.endswith(('.osm', '.xml', '.log', '.gml')):
                        filename = os.path.join(root, f)
                        text = create_text(filename, f)
                        href = filename.replace('html/', '')
                        url = link_template.format(href=href,
                                                   title=filename,
                                                   text=text)
                        if root.endswith('clean'):
                            excerpts_for_import.append(url)
                        elif f.endswith('%s.osm' % kommune_nr):
                            dataset_for_import.append(url)
                        elif 'NoName' in f or 'NoTags' in f:
                            excluded_from_import.append(url)
                        elif f.endswith(('.xml', '.gml')):
                            raw_data.append(url)
                        elif f.endswith('.log'):
                            log.append(url)
                        else:
                            pass # ignore

            row.append(fylke_nr)
            row.append("%s" % fylke_name)
            log.insert(0, "%s %s" % (kommune_nr, kommune_name))
            row.append(log)
            row.append(dataset_for_import)
            row.append(excerpts_for_import)            
            row.append(excluded_from_import)
            row.append(raw_data)

            table.append(row)

            last_update_stamp = os.path.getmtime(folder)
            last_update_datetime = datetime.fromtimestamp(last_update_stamp)
            last_update = last_update_datetime.strftime('%Y-%m-%d') # Note: date is now set by whatever row is 'last'

    return table, fylker, last_update

def main(data_dir='html/data/', root_output='html', template='html/template.html'):
    output_filename = os.path.join(root_output, 'index.html')
    
    table, fylker, last_update = create_main_table(data_dir, cache_dir=data_dir)
    write_template(template, output_filename, table=table, info=info,
                   fylker=fylker,
                   last_update=last_update)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='')
    argparse_util.add_verbosity(parser, default=logging.INFO)
    
    args = parser.parse_args()
    logging.basicConfig(level=args.loglevel)

    main()
