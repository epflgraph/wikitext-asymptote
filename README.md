# Wikitext Asymptote
Custom wikitext parser to produce html, plain text fields and relevant links from wikipedia page source code.

## Get started
To install the `wikitext_asymptote` package, simply run 

    pip install wikitext_asymptote

You can then use the package as follows:

    import wikitext_asymptote as wa

    # Raw wikitext goes here
    page = """..."""
    
    # Parse it
    parsed_page = wa.parse_page(page)

    # parsed_page contains fields for html, plain text or links
    print(parsed_page)

    # parsed_page = {
    #     'html': '...',
    #     'text': '...',
    #     'opening_text': '...',
    #     'auxiliary_text': [...],
    #     'heading': [...],
    #     'links': [...]
    # }

## About
This package was created to fulfill the precise needs for parsing wikitext in the context of the [EPFL Graph](https://www.epfl.ch/about/facts/epfl-graph/) project, which are a bit more involved than the defaults from `mwparserfromhell`.

However, the task of parsing wikitext taking into account all its syntax is gigantic. Already deciding, not even implementing, the parsing of each template in the myriad that's available, with all its variations, is virtually unfeasible.

Hence, the approach we have decided to commit to is that of _approximation_ (hence [Asymptote](https://en.wikipedia.org/wiki/Asymptote)). We try to parse a number of templates, tags and other entities as correctly as possible, in a way that _most_ cases are covered. In addition, we also have defaults, which may or may not be adequate for some cases. This implies that the parsed output is not perfect, and that is by design. From that point on, we work on a case-by-case basis to include parsing for new templates, tags or other entities, should the need arise. 

## Acknowledgements
Wikitext asymptote is built on top of the [`mwparserfromhell`](https://github.com/earwig/mwparserfromhell) package, so we acknowledge and are grateful for the work of their creators.  
