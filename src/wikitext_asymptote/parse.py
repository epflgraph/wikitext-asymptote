import re
import unicodedata
import mwparserfromhell
from mwparserfromhell.wikicode import Wikicode
from mwparserfromhell.nodes.argument import Argument
from mwparserfromhell.nodes.comment import Comment
from mwparserfromhell.nodes.external_link import ExternalLink
from mwparserfromhell.nodes.heading import Heading
from mwparserfromhell.nodes.html_entity import HTMLEntity
from mwparserfromhell.nodes.tag import Tag
from mwparserfromhell.nodes.template import Template
from mwparserfromhell.nodes.text import Text
from mwparserfromhell.nodes.wikilink import Wikilink

# Excluded sections
EXCLUDED_SECTIONS = {'references', 'references and notes', 'external links', 'footnotes', 'further reading'}
AUXILIARY_TEXT_SECTIONS = {'see also'}

# Ignored templates
IGNORED_TEMPLATES = {'sfn', 'efn', 'toc', 'anchor', 'vanchor', 'toc limit', 'toc_limit', 'toclimit', 'font color', 'clear',
                     'div col', 'div col end', 'cols', 'colbegin', 'colend', 'portal', 'portal inline',
                     'reflist', 'refbegin', 'refend', 'refn',
                     'citation needed', 'more citations needed section', 'expand section', 'update section',
                     'rp', 'convert', 'cite book', 'isbn', 'webarchive'}

# Relevant hatnotes
RELEVANT_HATNOTES = {'hatnote', 'about', 'distinguish', 'about-distinguish', 'for', 'for2', 'other uses', 'other uses of',
                     'other people', 'about other people', 'similar names', 'other places', 'other ships',
                     'other hurricanes', 'see also', 'further', 'short description', 'infobox'}

# Pronunciation & IPA link codes (https://en.wikipedia.org/wiki/Template:IPAc-en)
IPAC_MODIFIER_CODES = {'lang', 'local', 'ipa', 'also', 'uk', 'us', 'uklang', 'uslang', 'ukalso', 'usalso', 'alsouk', 'alsous'}

# File link variables (https://en.wikipedia.org/wiki/Wikipedia:Extended_image_syntax)
FILE_LINK_VARIABLES = {'thumb', 'frame', 'frameless', 'border', 'location', 'alignment', 'size', 'link', 'alt', 'page', 'langtag'}


############################################################


def concat(l, sep=''):
    return sep.join(l)


def clean(text):
    """
    Clean and normalizes text.
    """

    # Normalize line breaks and tabs
    text = re.sub('[\r\f\v]', '\n', text)
    text = re.sub('\t', ' ', text)

    # Strip lines
    lines = text.split('\n')
    text = '\n'.join([line.strip() for line in lines])

    # Remove lines with only punctuation
    text = re.sub('\n[,;.:+*·-]+', '\n', text)

    # Collapse consecutive line breaks
    text = re.sub('\n{2,}', '\n', text)

    # Collapse consecutive whitespaces
    text = re.sub(' +', ' ', text)

    # Normalize unicode characters
    text = unicodedata.normalize('NFKC', text)

    return text


def preprocess_text(text):
    # PROBLEM:
    #   Headings like ===''The Times They Are A-Changin''' sessions, part 1=== are not correctly parsed
    # WORKAROUND:
    #   1. Check if there are headings with an odd number of single quotes (').
    #   2. If so, replace all occurrences of ''[...]in''' with HTML tags <i>[...]in'</i>.
    #      For instance, ''The Times They Are A-Changin''' becomes <i>The Times They Are A-Changin'</i>.

    # Check for lines that start and end with the same number of = characters and contain at least one single quote (')
    matches = re.findall(r"^(=+)(.*'.*)\1$", text, re.MULTILINE)

    # For all matches, check if they contain an odd number of single quotes (')
    ok = True
    for _, match in matches:
        if match.count("'") % 2 != 0:
            ok = False
            break

    # If all headings are ok (contain an even number of single quotes (')), return the text unchanged
    if ok:
        return text

    # Replace all occurrences of ''[...]in''' with HTML tags <i>[...]in'</i>
    text = re.sub(r"''(.*in')''", r"<i>\1</i>", text)

    return text


############################################################


def parse_template(node):
    """
    Parse template node.

    Args:
        node (mwparserfromhell.nodes.Node): Node to parse.

    Returns:
        dict: Dictionary with keys 'html', 'text' and 'aux', containing the parsed text as html, plain text and
            auxiliary text, respectively, as lists of strings. Auxiliary text are hatnotes, captions, tables and html
            elements under the class 'searchaux', and they are excluded from the plain text.
    """

    # Initialise return object
    parsed_template = {
        'html': [],
        'text': [],
        'aux': []
    }

    # Extract template name
    name = str(node.name).lower().strip()

    # Full phonetic transcription of a word or expression
    if 'ipac' in name:
        for param in node.params:
            # Exclude named parameters, e.g. "audio=..."
            if param.showkey:
                continue

            # Parse parameter
            parsed_param = parse_node(param.value)

            # Exclude modifiers, e.g. "lang" or "US"
            if concat(parsed_param['text']) in IPAC_MODIFIER_CODES:
                continue

            for key in parsed_template:
                parsed_template[key].extend(parsed_param[key])

        return parsed_template

    # Phonetic transcription of a phoneme
    if 'ipa' in name:
        # First parameter should be the transcription
        if node.has(1):
            return parse_node(node.get(1).value)

        return parsed_template

    # Block in different language
    if 'lang' in name:
        # Case {{lang|fr|Bonjour}}
        if node.has(2):
            return parse_node(node.get(2).value)

        # Case {{lang-fr|Bonjour}}
        if node.has(1):
            return parse_node(node.get(1).value)

        return parsed_template

    # Floruit and circa templates
    if name in ['fl', 'fl.', 'circa', 'c.', 'born-in', 'born in', 'b.', 'died-in', 'died in', 'd.', 'married-in', 'married in', 'm.', 'reign', 'rexit', 'ruled', 'r.']:
        # First parameter
        if node.has(1):
            parsed_param = parse_node(node.get(1).value)

            for key in parsed_template:
                parsed_template[key].extend(parsed_param[key])

        # Second parameter is optional
        if node.has(2):
            parsed_param = parse_node(node.get(2).value)

            for key in parsed_template:
                if len(parsed_param[key]) > 0:
                    parsed_template[key].extend(['-'] + parsed_param[key])

        return parsed_template

    # Literal translations
    if name in ['literal translation', 'literally', 'lit', 'lit.']:
        # First parameter should be the translation
        if node.has(1):
            return parse_node(node.get(1).value)

        return parsed_template

    # Transliterations
    if name in ['transliteration']:
        # First parameter should be the translation
        if node.has(2):
            return parse_node(node.get(2).value)

        return parsed_template

    # Interlanguage links
    if 'ill' in name:
        if node.has(1):
            if node.has('lt'):
                return parse_node(node.get('lt').value)
            else:
                return parse_node(node.get(1).value)

        return parsed_template

    # Annotated links
    if name == 'annotated link':
        if node.has(1):
            return parse_node(node.get(1).value)

        return parsed_template

    # Nihongo: Kanji/kana segments
    if 'nihongo' in name:
        params = ['', '', '']

        for i in range(len(params)):
            if node.has(i + 1):
                params[i] = concat(parse_node(node.get(i + 1).value)['text'])

        s = ''
        if params[0] and params[1] and params[2]:
            s = f'{params[0]} ({params[1]}, {params[2]})'

        if params[0] and params[1]:
            s = f'{params[0]} ({params[1]})'

        if params[0] and params[2]:
            s = f'{params[0]} ({params[2]})'

        if params[1] and params[2]:
            s = f'{params[2]} ({params[1]})'

        if params[2]:
            s = params[2]

        if params[1]:
            s = params[1]

        if params[0]:
            s = params[0]

        if s:
            parsed_template['html'].append(s)
            parsed_template['text'].append(s)

        return parsed_template

    # Formatted number
    if 'val' in name:
        # Parameter p is the prefix
        if node.has('p'):
            parsed_param = parse_node(node.get('p').value)
            parsed_template['html'].extend(parsed_param['html'])
            parsed_template['text'].extend(parsed_param['text'])

        # First parameter is the number
        if node.has(1):
            parsed_param = parse_node(node.get(1).value)
            parsed_template['html'].extend(parsed_param['html'])
            parsed_template['text'].extend(parsed_param['text'])

        # Parameter e is the exponent
        if node.has('e'):
            parsed_param = parse_node(node.get('e').value)
            parsed_template['html'].extend(['e'] + parsed_param['html'])
            parsed_template['text'].extend(['e'] + parsed_param['text'])

        # Parameter u or ul is the unit (numerator)
        if node.has('u'):
            parsed_param = parse_node(node.get('u').value)
            parsed_template['html'].extend(parsed_param['html'])
            parsed_template['text'].extend(parsed_param['text'])
        elif node.has('ul'):
            parsed_param = parse_node(node.get('ul').value)
            parsed_template['html'].extend(parsed_param['html'])
            parsed_template['text'].extend(parsed_param['text'])

        # Parameter up or upl is the unit (denominator)
        if node.has('up'):
            parsed_param = parse_node(node.get('up').value)
            parsed_template['html'].extend(parsed_param['html'])
            parsed_template['text'].extend(parsed_param['text'])
        elif node.has('upl'):
            parsed_param = parse_node(node.get('upl').value)
            parsed_template['html'].extend(parsed_param['html'])
            parsed_template['text'].extend(parsed_param['text'])

        # Parameter s is the suffix
        if node.has('s'):
            parsed_param = parse_node(node.get('s').value)
            parsed_template['html'].extend(parsed_param['html'])
            parsed_template['text'].extend(parsed_param['text'])

        return parsed_template

    # Gap-separated values
    if 'gaps' in name:
        # Parameter lhs is the left hand-side
        if node.has('lhs'):
            parsed_param = parse_node(node.get('lhs').value)
            parsed_template['html'].extend(parsed_param['html'] + [' = '])
            parsed_template['text'].extend(parsed_param['text'] + [' = '])

        # Unnamed parameters constitute the number
        first = True
        for param in node.params:
            parsed_param = parse_node(param.value)
            if first:
                parsed_template['html'].extend(parsed_param['html'])
                parsed_template['text'].extend(parsed_param['text'])
                first = False
            else:
                parsed_template['html'].extend([' '] + parsed_param['html'])
                parsed_template['text'].extend([' '] + parsed_param['text'])

        # Parameter e is the exponent, base is the base
        if node.has('e'):
            parsed_exp = parse_node(node.get('e').value)
            if node.has('base'):
                parsed_base = parse_node(node.get('base').value)
                parsed_template['html'].extend([' × '] + parsed_base['html'] + ['<sup>'] + parsed_exp['html'] + ['</sup>'])
                parsed_template['text'].extend([' × '] + parsed_base['text'] + ['^'] + parsed_exp['text'])
            else:
                parsed_template['html'].extend([' × '] + ['10'] + ['<sup>'] + parsed_exp['html'] + ['</sup>'])
                parsed_template['text'].extend([' × '] + ['10'] + ['^'] + parsed_exp['text'])

        # Parameter u is the unit
        if node.has('u'):
            parsed_param = parse_node(node.get('u').value)
            parsed_template['html'].extend([' '] + parsed_param['html'])
            parsed_template['text'].extend([' '] + parsed_param['text'])

        return parsed_template

    # Spaces
    if 'space' in name or 'nbsp' in name:
        parsed_template['html'].append('&nbsp;')
        parsed_template['text'].append(' ')
        return parsed_template

    # Dashes
    if name in ['dash', 'snd', 'spnd', 'sndash', 'spndash', 'spaced en dash']:
        parsed_template['html'].append('&nbsp;&ndash; ')
        parsed_template['text'].append(' - ')
        return parsed_template

    # = template
    if name == '=':
        parsed_template['html'].append('=')
        parsed_template['text'].append('=')

        return parsed_template

    # Nowrap
    if 'nowrap' in name:
        for param in node.params:
            parsed_param = parse_node(param.value)
            parsed_template['html'].extend(['<span class="nowrap">'] + parsed_param['html'] + ['</span>'])
            parsed_template['text'].extend(parsed_param['text'])

        return parsed_template

    # Greek letters
    if name in ['gamma', 'epsilon', 'varepsilon', 'theta', 'vartheta', 'kappa', 'lambda', 'mu', 'pi', 'sigma', 'varsigma', 'tau', 'upsilon', 'phi', 'varphi', 'xi']:
        parsed_template['html'].append(f'&{name};')
        parsed_template['text'].append(name)

        return parsed_template

    # Abbreviation
    if 'abbr' in name:
        if node.has(1) and node.has(2):
            parsed_abbr = parse_node(node.get(1))
            parsed_title = parse_node(node.get(2))

            parsed_template['html'].extend(['<abbr title="'] + parsed_title['html'] + ['">'] + parsed_abbr['html'] + ['</abbr>'])
            parsed_template['text'].extend(parsed_title['text'] + [' ('] + parsed_abbr['text'] + [')'])

        return parsed_template

    if 'math' in name:
        if node.has(1):
            return parse_node(node.get(1).value)

    # Mathematical variable mvar
    if 'mvar' in name:
        if node.has(1):
            parsed_param = parse_node(node.get(1).value)
            parsed_template['html'].extend(['<math>'] + [str(node.get(1).value)] + ['</math>'])
            parsed_template['text'].extend(parsed_param['text'])

        return parsed_template

    # Mathematical fraction sfrac
    if 'sfrac' in name:
        if node.has(1):
            parsed_param_1 = parse_node(node.get(1).value)

            if node.has(2):
                parsed_param_2 = parse_node(node.get(2).value)

                if node.has(3):
                    # {{sfrac|A|B|C}} means AB/C
                    parsed_param_3 = parse_node(node.get(3).value)
                    parsed_template['html'].extend(['<math>'] + [str(node.get(1).value)] + [str(node.get(2).value)] + ['/'] + [str(node.get(1).value)] + ['</math>'])
                    parsed_template['text'].extend(parsed_param_1['text'] + [' '] + parsed_param_2['text'] + ['/'] + parsed_param_3['text'])
                else:
                    # {{sfrac|A|B}} means A/B
                    parsed_template['html'].extend(['<math>'] + [str(node.get(1).value)] + ['/'] + [str(node.get(2).value)] + ['</math>'])
                    parsed_template['text'].extend(parsed_param_1['text'] + ['/'] + parsed_param_2['text'])
            else:
                # {{sfrac|A}} means 1/A
                parsed_template['html'].extend(['<math>'] + ['1'] + ['/'] + [str(node.get(1).value)] + ['</math>'])
                parsed_template['text'].extend(['1'] + ['/'] + parsed_param_1['text'])

        return parsed_template

    # Subscripts
    if 'sub' in name:
        if node.has(1):
            # First parameter should be the subscripted expression
            parsed_param = parse_node(node.get(1).value)
            parsed_template['html'].extend(['<sub>'] + [str(node.get(1).value)] + ['</sub>'])
            parsed_template['text'].extend(['_'] + parsed_param['text'])

        return parsed_template

    # Superscripts
    if 'sup' in name:
        if node.has(1):
            # First parameter should be the superscripted expression
            parsed_param = parse_node(node.get(1).value)
            parsed_template['html'].extend(['<sup>'] + [str(node.get(1).value)] + ['</sup>'])
            parsed_template['text'].extend(['^'] + parsed_param['text'])

        return parsed_template

    # Chem
    if name == 'chem':
        for param in node.params:
            parsed_param = parse_node(param.value)
            parsed_template['html'].extend(parsed_param['html'])
            parsed_template['text'].extend(parsed_param['text'])

        return parsed_template

    # Main article template. This template creates a link but is not a Wikilink object.
    if 'main' in name or 'see also' in name:
        # Parse all parameters, prioritize named parameters l3 to unnamed 3
        parsed_params = []
        for i in range(len(node.params)):
            if node.has(i + 1):
                if node.has(f'l{i + 1}'):
                    parsed_params.append(parse_node(node.get(f'l{i + 1}').value))
                else:
                    parsed_params.append(parse_node(node.get(i + 1).value))

        # If no parameters, return empty
        if len(parsed_params) == 0:
            return parsed_template

        # If one parameter, return that parsed parameter
        if len(parsed_params) == 1:
            parsed_template['html'].extend(parsed_params[0]['html'])
            parsed_template['text'].extend(parsed_params[0]['text'])
            return parsed_template

        # Return all parameters in the format "XXX, YYY and ZZZ"
        first = True
        for parsed_param in parsed_params[:-1]:
            if first:
                parsed_template['html'].extend(parsed_param['html'])
                parsed_template['text'].extend(parsed_param['text'])
            else:
                parsed_template['html'].extend([', '] + parsed_param['html'])
                parsed_template['text'].extend([', '] + parsed_param['text'])

        parsed_template['html'].extend([' and '] + parsed_params[-1]['html'])
        parsed_template['text'].extend([' and '] + parsed_params[-1]['text'])

        return parsed_template

    # Quote template
    if 'quote' in name:
        if node.has('text'):
            return parse_node(node.get('text').value)

        if node.has(1):
            return parse_node(node.get(1).value)

        return parsed_template

    # Templates to be ignored
    if name in IGNORED_TEMPLATES:
        return parsed_template

    # Default behaviour for Template is return empty
    return parsed_template


def parse_node(node):
    """
    Parse node.

    Args:
        node (mwparserfromhell.nodes.Node): Node to parse.

    Returns:
        dict: Dictionary with keys 'html', 'text' and 'aux', containing the parsed text as html, plain text and
            auxiliary text, respectively, as lists of strings. Auxiliary text are hatnotes, captions, tables and html
            elements under the class 'searchaux', and they are excluded from the plain text.
    """

    # Initialise return object
    parsed_node = {
        'html': [],
        'text': [],
        'aux': []
    }

    # node is actually None
    if node is None:
        return parsed_node

    # Wikicode node. We parse all its children and concatenate the output
    if isinstance(node, Wikicode):
        for child in node.nodes:
            parsed_child = parse_node(child)

            for key in parsed_node:
                parsed_node[key].extend(parsed_child[key])

        return parsed_node

    # Argument node
    if isinstance(node, Argument):
        s = str(node)
        parsed_node['html'] = s
        parsed_node['text'] = s
        return parsed_node

    # Comment node. We ignore it.
    if isinstance(node, Comment):
        return parsed_node

    # External link node
    if isinstance(node, ExternalLink):
        parsed_title = parse_node(node.title)
        parsed_url = parse_node(node.url)

        parsed_node['html'].append(f"""<a href="{concat(parsed_url['html'])}">{concat(parsed_title['html'])}</a>""")
        parsed_node['text'].extend(parsed_title['text'])

        return parsed_node

    # Heading node
    if isinstance(node, Heading):
        parsed_title = parse_node(node.title)

        parsed_node['html'].append(f"""<h{node.level}>{concat(parsed_title['html'])}</h{node.level}>""")

        return parsed_node

    # HTML entity node (like &nbsp;)
    if isinstance(node, HTMLEntity):
        parsed_node['html'].append(str(node))
        parsed_node['text'].append(node.normalize())

        return parsed_node

    # Tag nodes have wikicode as content
    if isinstance(node, Tag):
        # Tag is self-closing, like <br> or <img/>
        if node.self_closing:
            parsed_node['html'].append(str(node))
            return parsed_node

        tag = str(node.tag)

        # We exclude ref tags
        if tag in ['ref']:
            return parsed_node

        # Tables are auxiliary text
        if tag in ['table']:
            parsed_contents = parse_node(node.contents)
            parsed_node['aux'].extend(parsed_contents['text'])
            return parsed_node

        # Convert math to LaTeX
        if tag in ['math']:
            parsed_node['html'].append(str(node))
            return parsed_node

            # # Escape backslashes
            # s = s.replace('\\', '\\\\')
            #
            # # Wrap with dollar signs for latex
            # s = f'${s}$'
            #
            # return s

        # Parse tag contents by default
        return parse_node(node.contents)

    # Template node
    if isinstance(node, Template):
        return parse_template(node)

    # Text node
    if isinstance(node, Text):
        # Need to check for wrongly matched templates due to a mwparserfromhell limitation
        # concerning template transclusion.
        #
        # e.g. {{DISPLAYTITLE:SL<sub>2</sub>('''R''')}} is parsed as
        #   - Text node {{DISPLAYTITLE:SL
        #   - Tag node <sub>2</sub>
        #   - Text node (
        #   - Tag node '''R'''
        #   - Text node )}}
        #
        # instead of as a Template node. We correct the Text nodes containing unmatched {{ or }}
        # as a patch to this behavior. In the previous example, we return the string
        #   DISPLAYTITLE:SL2(R)
        #
        # More info: https://github.com/earwig/mwparserfromhell#limitations

        text = node.value
        if '{{' in text and '}}' not in text:
            s = ''.join(text.split('{{'))
            parsed_node['html'].append(s)
            parsed_node['text'].append(s)
            return parsed_node
        if '{{' not in text and '}}' in text:
            s = ''.join(text.split('}}'))
            parsed_node['html'].append(s)
            parsed_node['text'].append(s)
            return parsed_node

        parsed_node['html'].append(text)
        parsed_node['text'].append(text)
        return parsed_node

    # Wikilink nodes. We exclude some types, otherwise parse inner text
    if isinstance(node, Wikilink):
        # Parse captions for files, images and categories
        for link_type in ['file', 'image', 'category']:
            if link_type in str(node.title).lower():
                if node.text is not None:
                    # Remove all parameters except last one, which should be the caption
                    caption = concat(parse_node(node.text)['text']).split('|')[-1]
                    parsed_node['aux'].append(caption)

                return parsed_node

        # If the link has text, parse it and return it
        if node.text is not None:
            return parse_node(node.text)

        # Otherwise parse link title
        return parse_node(node.title)

    return parsed_node


def parse_hatnote(node):
    """
    Parse hatnote node.

    Args:
        node (mwparserfromhell.nodes.Template): Node to parse.

    Returns:
        str: Parsed node as text.
    """

    # Hatnotes can only be templates
    if not isinstance(node, Template):
        return ''

    # Extract template name
    name = str(node.name).lower().strip()

    # Return empty if hatnote not relevant
    if name not in RELEVANT_HATNOTES and 'infobox' not in name:
        return ''

    if 'infobox' in name and node.has('caption'):
        return concat(parse_node(node.get('caption').value)['text'], sep=' ')

    # For the "About" hatnote, only the first child is returned, the rest are disambiguation alternatives
    if 'about' in name and node.params:
        return concat(parse_node(node.params[0].value)['text'], sep=' ')

    # Concatenate all parsed parameters by default. This could be perhaps refined depending on the template.
    return concat([concat(parse_node(param.value)['text'], sep=' ') for param in node.params], sep=' ')


def parse_section(section):
    # Extract list of section headings and title
    section_headings = [clean(concat(parse_node(heading.title)['text'])) for heading in section.filter_headings()]
    section_title = section_headings[0] if section_headings else ''
    section_title = clean(section_title.lower())

    # Initialise object to return
    parsed_section = {
        'html': [],
        'text': [],
        'opening_text': [],
        'auxiliary_text': [],
        'heading': section_headings
    }

    # The first section is the only one that is included in opening_text
    first_section = not section_title
    hatnotes_expected = True
    for node in section.nodes:
        # Hatnotes can only be Templates, and we ignore empty Text nodes as well
        if hatnotes_expected:
            if isinstance(node, Text) and not node.value.strip():
                continue

            # Process hatnotes and continue
            if isinstance(node, Template):
                parsed_hatnote = parse_hatnote(node)

                if parsed_hatnote:
                    parsed_section['auxiliary_text'].append(parsed_hatnote)

                continue

        # Default behaviour
        hatnotes_expected = False
        parsed_node = parse_node(node)

        # HTML and auxiliary_text are always included
        parsed_section['html'].extend(parsed_node['html'])
        parsed_section['auxiliary_text'].extend(parsed_node['aux'])

        if section_title in AUXILIARY_TEXT_SECTIONS:
            parsed_section['auxiliary_text'].extend(parsed_node['text'])
        else:
            parsed_section['text'].extend(parsed_node['text'])

        if first_section:
            parsed_section['opening_text'].extend(parsed_node['text'])

    return parsed_section


def section_is_wanted(heading):
    """
    Returns whether we want to keep a section of a page based on its title. Typically, we want to keep regular content,
    and we want to exclude references, etc.
    """
    heading_lower = clean(heading.lower())
    return heading_lower not in EXCLUDED_SECTIONS


def link_is_wanted(link):
    """
    Returns whether we want to keep a wikilink.
    """
    title = str(link.title)

    # If there is no ':', target namespace is (main), we keep the link
    if ':' not in title:
        return True

    # We accept links like [[:Mathematics]], otherwise we reject it
    prefix = title.split(':')[0]
    return len(prefix) == 0


def get_link_title(link):
    """
    Parses and cleans up the title of the target page given a wikilink.
    """
    # Extract title as string
    title = str(link.title)

    # Delete part of the link to a specific element in the page, so that we keep only the page title
    title = title.split('#')[0]

    # Return title with capital first letter and replacing spaces with underscores
    return title.capitalize().replace(' ', '_')


def parse_page(page_content):
    # Preprocess page content
    page_content = preprocess_text(page_content)

    # Produce wikicode object from page content
    wikicode = mwparserfromhell.parse(page_content)

    # Split into sections
    sections = wikicode.get_sections(levels=[2], include_lead=True, matches=section_is_wanted)

    # Initialise object to return
    parsed_page = {
        'html': [],
        'text': [],
        'opening_text': [],
        'auxiliary_text': [],
        'heading': [],
        'links': []
    }

    # Parse each section separately and concatenate their outputs
    for section in sections:
        parsed_section = parse_section(section)

        for key in parsed_section:
            parsed_page[key].extend(parsed_section[key])

        links = section.filter(matches=link_is_wanted, forcetype=Wikilink)
        links = [get_link_title(link) for link in links]
        parsed_page['links'].extend(links)

    # Concatenate and clean the text fields
    parsed_page['html'] = concat(parsed_page['html'])
    parsed_page['text'] = clean(concat(parsed_page['text']))
    parsed_page['opening_text'] = clean(concat(parsed_page['opening_text']))

    parsed_page['auxiliary_text'] = [clean(aux).replace('\n', '') for aux in parsed_page['auxiliary_text']]
    parsed_page['auxiliary_text'] = [aux for aux in parsed_page['auxiliary_text'] if len(aux) > 1]

    return parsed_page
