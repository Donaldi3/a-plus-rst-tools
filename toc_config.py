import re
from docutils import nodes
from sphinx import addnodes

import aplus_nodes
import yaml_writer


def prepare(app):
    ''' Prepares environment for configuration values. '''
    yaml_writer.create_directory(app)


def write(app, exception):
    ''' Writes the table of contents level configuration. '''
    if exception:
        return

    course_open = app.config.course_open_date
    course_close = app.config.course_close_date

    modules = []
    category_keys = []

    def traverse_tocs(doc):
        names = []
        for toc in doc.traverse(addnodes.toctree):
            for _,docname in toc.get('entries', []):
                names.append(docname)
        return [(name,app.env.get_doctree(name)) for name in names]

    def first_title(doc):
        titles = doc.traverse(nodes.title)
        return titles[0].astext() if titles else 'Unnamed'

    # Tries to parse date from natural text.
    def parse_date(src):
        d,t = src.split(' ', 1)
        if re.match('^\d\d.\d\d.\d\d\d\d$', d):
            ds = d.split('.')
            d = ds[2] + '-' + ds[1] + '-' + ds[0]
        elif not re.match('^\d\d-\d\d-\d\d\d\d$', d):
            return None
        if not re.match('^\d\d(:\d\d(:\d\d)?)?$', t):
            t = '12:00'
        return d + ' ' + t

    # Recursive chapter parsing.
    def parse_chapter(docname, doc, parent):
        for config_file in [e.yaml_write for e in doc.traverse(aplus_nodes.html) if e.has_yaml('exercise')]:
            config = yaml_writer.read(config_file)
            if config.get('_external', False):
                exercise = config.copy()
                del exercise['_external']
            else:
                exercise = {
                    'key': config['key'],
                    'config': config['key'] + '.yaml',
                    'max_submissions': config['max_submissions'],
                    'max_points': config['max_points'],
                    'points_to_pass': config['points_to_pass'],
                    'category': config['category'],
                }
            exercise.update({
                'allow_assistant_grading': False,
                'status': 'unlisted',
            })
            parent.append(exercise)
            if not config['category'] in category_keys:
                category_keys.append(config['category'])

        for name,child in traverse_tocs(doc):
            chapter = {
                'key': name.replace('/', '_'),#name.split('/')[-1],
                'name': first_title(child),
                'static_content': name + '.html',
                'category': 'chapter',
                'use_wide_column': app.config.use_wide_column,
                'children': [],
            }
            parent.append(chapter)
            if not 'chapter' in category_keys:
                category_keys.append('chapter')
            parse_chapter(name, child, chapter['children'])

    root = app.env.get_doctree(app.config.master_doc)
    course_title = first_title(root)

    # Traverse the documents using toctree directives.
    title_date_re = re.compile('.*\(DL (.+)\)')
    for docname,doc in traverse_tocs(root):
        title = first_title(doc)
        match = title_date_re.match(title)
        module_close = parse_date(match.group(1)) if match else None
        module = {
            'key': docname.split('/')[0],
            'name': title,
            'open': course_open,
            'close': module_close or course_close,
            'children': [],
        }
        modules.append(module)
        parse_chapter(docname, doc, module['children'])

    # Create categories.
    categories = {key: {'name': key} for key in category_keys}

    # Get relative out dir.
    i = 0
    while i < len(app.outdir) and i < len(app.confdir) and app.outdir[i] == app.confdir[i]:
        i += 1
    if app.outdir[i] == '/':
        i += 1
    outdir = app.outdir[i:]

    # Write the configuration index.
    yaml_writer.write(
        yaml_writer.file_path(app.env, 'index'),
        {
            'name': course_title,
            'language': app.config.language,
            'static_dir': outdir,
            'start': course_open,
            'end': course_close,
            'modules': modules,
            'categories': categories,
        }
    )