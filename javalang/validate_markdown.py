#!/usr/bin/env python
# -*- coding: utf-8 -*-

#  Copyright © 2016 Cask Data, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.


import javalang
import sys

from argparse import ArgumentParser
from BeautifulSoup import BeautifulSoup
from markdown import markdown

# Constants
PROPERTIES_DELIMITER = 'Properties\n----------'
PROPERTY_NAME_START = '**'
PROPERTY_NAME_END = ':**'
NEXT_PROPERTY_DELIMITER = '\n\n'
EXAMPLE_DELIMITER = 'Example\n-------'
TERMINAL_SUPERCLASS = 'PluginConfig'


def setup_args():
    parser = ArgumentParser(description='Validate Hydrator Plugin Markdown Consistency')
    parser.add_argument('--markdown', help='Path to the markdwon (.md) file.')
    parser.add_argument('--plugin', help='Path to plugin (.java) file.')
    parser.add_argument('--strict', action='store_true',
                        help='Causes the validator to throw an exception when encountering an inconsistency.')
    parser.add_argument('--showdiff', action='store_true', help='Prints descriptions of markdown property ' +
                                                                'inconsistencies to output.')
    return parser.parse_args()


def parse_file(config_class_file_path):
    with open(config_class_file_path, 'r') as java_file:
        file_contents = java_file.read()
    tree = javalang.parse.parse(file_contents)
    if len(tree.types) == 0:
        raise Exception('Class not found: Unable to find Java class in ' + sys.argv[1])
    return tree


def get_class_signature(class_declaration):
    class_signature = class_declaration.name
    if class_declaration.extends is not None:
        class_signature += ' extends ' + class_declaration.extends.name
    if class_declaration.implements is not None:
        class_signature += ' implements ' + ', '.join([interface.name for interface in class_declaration.implements])
    return class_signature


def reconstruct_argument(argument_piece):
    if argument_piece.__class__.__name__ == 'Literal':
        # strip opening and closing double quotes
        return argument_piece.value[1:-1]
    elif argument_piece.__class__.__name__ != 'BinaryOperation':
        raise Exception('Unsupported annotation operation: ' + argument_piece.__class__.__name__)
    else:
        return reconstruct_argument(argument_piece.operandl) + reconstruct_argument(argument_piece.operandr)


def get_annotation_argument(children):
    if children[1] is None:
        return ''
    else:
        return reconstruct_argument(children[1])  # children[1] is the first and assumed only argument


def get_plugin_properties(class_declaration):
    plugin_properties = {}
    for field_declaration in class_declaration.fields:
        field_annotations = {}
        for annotation in field_declaration.annotations:
            field_annotations[annotation.name] = get_annotation_argument(annotation.children)
        plugin_properties[field_declaration.declarators[0].name] = field_annotations
    return plugin_properties


def parse_property_names_from_markdown(properties_section):
    markdown_properties = {}

    while properties_section:
        # Find property name
        name_start_index = properties_section.find(PROPERTY_NAME_START)
        name_end_index = properties_section.find(PROPERTY_NAME_END)
        if name_end_index is -1 or name_end_index is -1:
            raise Exception('Unable to match valid property syntax: **propertyName:**')
        property_name = properties_section[name_start_index + len(PROPERTY_NAME_START):name_end_index]

        # Find property description
        next_property_index = properties_section.find(NEXT_PROPERTY_DELIMITER)
        property_description = properties_section[name_end_index + len(PROPERTY_NAME_END):next_property_index]
        markdown_properties[property_name] = property_description

        # Finish searching remainder of section
        properties_section = properties_section[next_property_index + len(NEXT_PROPERTY_DELIMITER):]
    return markdown_properties


def parse_markdown_file(markdown_file_path):
    # Read file contents
    with open(markdown_file_path, 'r') as markdown_file:
        file_contents = markdown_file.read()

    # Find property section
    property_index = file_contents.find(PROPERTIES_DELIMITER)
    example_index = file_contents.find(EXAMPLE_DELIMITER)

    markdown_filename = markdown_file_path[markdown_file_path.rfind('/') + 1:]
    if property_index is -1:
        raise Exception('Properties section not found: Unable to find property section in ' +
                        markdown_filename + ' delimited by ' + PROPERTIES_DELIMITER + '.')
    elif example_index is -1:
        raise Exception('Example section not found: Unable to find example section in ' +
                        markdown_filename + ' delimited by ' + EXAMPLE_DELIMITER + '.')
    elif example_index < property_index:
        raise Exception('Example section found before properties section in ' + markdown_filename)

    properties_section = file_contents[property_index + len(PROPERTIES_DELIMITER):example_index]
    return parse_property_names_from_markdown(properties_section)


def print_notice(strict, description):
    if strict:
        raise Exception('ERROR: ' + description)
    else:
        print('WARNING: ' + description)
    print


def validate_properties_present(config_filename, markdown_filename, plugin_properties, markdown_properties, args):
    # Validate plugin properties are in markdown file
    for plugin_property in plugin_properties:
        if plugin_property not in markdown_properties:
            print_notice(args.strict, 'Property ' + plugin_property + ' in ' + config_filename +
                         ' not present in markdown file ' + markdown_filename)

    # Validate markdown properties are in plugin config
    for markdown_property in markdown_properties:
        if markdown_property not in plugin_properties:
            print_notice(args.strict, 'Property ' + markdown_property + ' in ' + markdown_filename +
                         ' not present in config class ' + config_filename + '.')


def validate_descriptions_match(config_filename, markdown_filename, plugin_properties, markdown_properties, args):
        for plugin_property in plugin_properties:
            plugin_description = plugin_properties[plugin_property]['Description']
            if not plugin_description:
                print_notice(args.strict, 'Property ' + plugin_property + ' has no description specified in config ' +
                             'class' + config_filename + '.')
            else:
                # Strip markdown format from description
                raw_markdown_description = markdown(markdown_properties[plugin_property])
                markdown_description = ''.join(BeautifulSoup(raw_markdown_description).findAll(text=True))
                if not markdown_description:
                    print_notice(args.strict, 'Property ' + plugin_property + ' has no description specified in ' +
                                 'markdown file ' + markdown_filename)

                markdown_description = markdown_description.replace('\n', ' ')
                if not markdown_description.startswith(plugin_description):
                    print_notice(args.strict, 'Description of property ' + plugin_property + ' in markdown file ' +
                                 markdown_filename + ' does not begin with the same description found in the config ' +
                                 'class ' + config_filename + '.')
                    if args.showdiff:
                        print('\t* Plugin:\t' + plugin_description)
                        print('\t* Markdown:\t' + markdown_description)
                        print


def main():
    # Setup arguments once to avoid redundant checks
    args = setup_args()

    # Parse the Java file
    config_class_file_path = args.plugin
    tree = parse_file(config_class_file_path)

    # Get class information
    class_declaration = tree.types[0]

    # Get config properties
    plugin_properties = get_plugin_properties(class_declaration)

    # Parse the markdown file
    markdown_file_path = args.markdown
    markdown_properties = parse_markdown_file(markdown_file_path)

    config_filename = config_class_file_path[config_class_file_path.rfind('/') + 1:]
    markdown_filename = markdown_file_path[markdown_file_path.rfind('/') + 1:]

    # Print class information
    class_name = class_declaration.name
    header = 'Validating ' + class_name + ' against ' + markdown_filename
    print('=' * len(header) + '\n' + header + '\n' + '=' * len(header) + '\n')

    # Begin validating properties
    validate_properties_present(config_filename, markdown_filename, plugin_properties, markdown_properties, args)
    validate_descriptions_match(config_filename, markdown_filename, plugin_properties, markdown_properties, args)


if __name__ == "__main__":
    main()
