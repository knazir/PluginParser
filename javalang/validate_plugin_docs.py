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
import os

from argparse import ArgumentParser
from BeautifulSoup import BeautifulSoup
from markdown import markdown

# Plugin Constants
IGNORED_FILES = ['package-info.java']

# Redundant key-value pairs required because code is not consistent in how annotation arguments are specified
PLUGIN_TYPES = {
    "BatchSink.PLUGIN_TYPE": "batchsink",
    "batchsink": "batchsink",

    "BatchSource.PLUGIN_TYPE": "batchsource",
    "batchsource": "batchsource",

    "RealtimeSink.PLUGIN_TYPE": "realtimesink",
    "realtimesink": "realtimesink",

    "RealtimeSource.PLUGIN_TYPE": "realtimesource",
    "realtimesource": "realtimesource",

    "StreamingSource.PLUGIN_TYPE": "streamingsource",
    "streamingsource": "streamingsource",

    "SparkSink.PLUGIN_TYPE": "sparksink",
    "sparksink": "sparksink",

    "SparkCompute.PLUGIN_TYPE": "sparkcompute",
    "sparkcompute": "sparkcompute",

    "Transform.PLUGIN_TYPE": "transform",
    "transform": "transform",

    "Action.PLUGIN_TYPE": "action",
    "action": "action",

    "PostAction.PLUGIN_TYPE": "postaction",
    "postaction": "postaction"
}

# Markdown Constants
PROPERTIES_DELIMITERS = ['Properties\n----------', 'Configuration\n-------------']
PROPERTY_NAME_START = '**'
PROPERTY_NAME_END = ':**'
NEXT_PROPERTY_DELIMITER = '\n\n'
EXAMPLE_DELIMITERS = ['Example\n-------', 'Examples\n--------']
TERMINAL_SUPERCLASS = 'PluginConfig'


def setup_args():
    parser = ArgumentParser(description='Validate Hydrator Plugin Markdown Consistency')
    parser.add_argument('--path', help='The path to the Hydrator Plugins repository.')
    parser.add_argument('--strict', action='store_true',
                        help='Causes the validator to throw an exception when encountering an inconsistency.')
    parser.add_argument('--showdiff', action='store_true', help='Prints descriptions of markdown property ' +
                                                                'inconsistencies to output.')
    return parser.parse_args()


def parse_file(config_class_file_path, class_filename):
    with open(config_class_file_path, 'r') as java_file:
        file_contents = java_file.read()
    tree = javalang.parse.parse(file_contents)
    if len(tree.types) == 0:
        raise Exception('Class not found: Unable to find Java class in "' + class_filename + ".")
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
    elif argument_piece.__class__.__name__ == 'BinaryOperation':
        return reconstruct_argument(argument_piece.operandl) + reconstruct_argument(argument_piece.operandr)
    elif argument_piece.__class__.__name__ == 'MemberReference':
        return argument_piece.qualifier + '.' + argument_piece.member
    elif argument_piece.__class__.__name__ == 'list':
        # Assumed to be ElementValuePair where element of interest is on right-hand-side
        return reconstruct_argument(argument_piece[0].children[1])
    else:
        raise Exception('Unsupported annotation operation: ' + argument_piece.__class__.__name__)


def get_annotation_argument(children):
    if children[1] is None:
        return ''
    else:
        return reconstruct_argument(children[1])  # children[1] is the first and assumed only argument


def get_config_class(class_declaration):
    class_name = unicode_to_ascii(class_declaration.name)
    if class_name.endswith('Config'):
        return class_declaration
    elif class_name.endswith('Test'):
        return None
    for child_declaration in class_declaration.children:
        if isinstance(child_declaration, list):
            for item in child_declaration:
                if item.__class__.__name__ == 'ClassDeclaration' and unicode_to_ascii(item.name).endswith('Config'):
                    return item
    return None


def unicode_to_ascii(u_str):
    return u_str.encode('ascii', 'ignore')


def is_abstract(plugin_class_declaration):
    for modifier in plugin_class_declaration.modifiers:
        if unicode_to_ascii(modifier) == 'abstract':
            return True


def plugin_type_from_annotation(annotation):
    plugin_type = unicode_to_ascii(get_annotation_argument(annotation.children))
    result = PLUGIN_TYPES[plugin_type]
    if result is None:
        raise Exception("Encountered invalid plugin type " + plugin_type + " is not valid.")
    return result


def get_plugin_properties(plugin_class_declaration):
    plugin_properties = {}
    for annotation in plugin_class_declaration.annotations:
        if annotation.name == 'Plugin':
            plugin_properties['type'] = plugin_type_from_annotation(annotation)
        elif annotation.name == 'Name':
            plugin_properties['name'] = get_annotation_argument(annotation.children)
    if 'type' not in plugin_properties:
        raise Exception('Unable to parse "plugin" property for plugin ' + plugin_class_declaration.name)
    if 'name' not in plugin_properties:
        raise Exception('Unable to parse "name" property for plugin ' + plugin_class_declaration.name)
    return plugin_properties


def get_plugin_config_properties(config_class_declaration):
    plugin_properties = {}
    for field_declaration in config_class_declaration.fields:
        field_annotations = {}
        for annotation in field_declaration.annotations:
            field_annotations[annotation.name] = get_annotation_argument(annotation.children)
        plugin_properties[field_declaration.declarators[0].name] = field_annotations
    return plugin_properties


def parse_property_names_from_markdown(properties_section):
    markdown_properties = {}

    while properties_section and properties_section != '\n':
        # Find property name
        name_start_index = properties_section.find(PROPERTY_NAME_START)
        name_end_index = properties_section.find(PROPERTY_NAME_END)
        if name_end_index is -1 or name_end_index is -1:
            break
        property_name = properties_section[name_start_index + len(PROPERTY_NAME_START):name_end_index]

        # Find property description
        next_property_index = properties_section.find(NEXT_PROPERTY_DELIMITER)
        property_description = properties_section[name_end_index + len(PROPERTY_NAME_END):next_property_index]
        markdown_properties[property_name] = property_description

        # Finish searching remainder of section
        properties_section = properties_section[next_property_index + len(NEXT_PROPERTY_DELIMITER):]
    return markdown_properties


def find_markdown_file(plugin_path, plugin_properties):
    docs_path = plugin_path[:plugin_path.rfind('/src')] + '/docs/'
    return docs_path + plugin_properties['name'] + '-' + plugin_properties['type'] + '.md'


def try_to_find(contents, delims):
    for delimiter in delims:
        index = contents.find(delimiter)
        if index != -1:
            return index
    return -1


def parse_markdown_file(markdown_file_path, markdown_filename, args):
    try:
        # Read file contents
        with open(markdown_file_path, 'r') as markdown_file:
            file_contents = markdown_file.read()

        # Find property section
        property_index = try_to_find(file_contents, PROPERTIES_DELIMITERS)
        example_index = try_to_find(file_contents, EXAMPLE_DELIMITERS)

        if property_index == -1:
            print_notice(args.strict, 'Unable to find property section in "' + markdown_filename +
                         '" delimited by:\n' + '\nor\n'.join(PROPERTIES_DELIMITERS) + '')
        elif example_index == -1:
            print_notice(args.strict, 'Unable to find example section in "' + markdown_filename +
                         '" delimited by:\n' + '\nor\n'.join(EXAMPLE_DELIMITERS) + '')
        elif example_index < property_index:
            print_notice(args.strict, 'Example section found before properties section in "' + markdown_filename + '".')

        # TODO: change to length of specific delimiter found
        properties_section = file_contents[property_index + len(PROPERTIES_DELIMITERS[0]):example_index]
        return parse_property_names_from_markdown(properties_section)
    except IOError:
        print_notice(args.strict, 'Unable to find markdown file "' + markdown_file_path + '".')
        return None


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
            print_notice(args.strict, 'Property "' + plugin_property + '" in "' + config_filename +
                         '" not present in markdown file "' + markdown_filename + '".')

    # Validate markdown properties are in plugin config
    for markdown_property in markdown_properties:
        if markdown_property not in plugin_properties:
            print_notice(args.strict, 'Property "' + markdown_property + '" in "' + markdown_filename +
                         '" not present in config class "' + config_filename + '".')


def validate_descriptions_match(config_filename, markdown_filename, plugin_properties, markdown_properties, args):
        for plugin_property in plugin_properties:
            try:
                plugin_description = plugin_properties[plugin_property]['Description']
            except KeyError:
                print_notice(args.strict, 'Property "' + plugin_property + '" has no description specified in "' +
                             config_filename + '".')
                continue

            if not plugin_description:
                print_notice(args.strict, 'Property "' + plugin_property + '" has no description specified in config ' +
                             'class "' + config_filename + '".')
            else:
                try:
                    # Strip markdown format from description
                    raw_markdown_description = markdown(markdown_properties[plugin_property])
                    markdown_description = ''.join(BeautifulSoup(raw_markdown_description).findAll(text=True))
                    if not markdown_description:
                        print_notice(args.strict, 'Property ' + plugin_property + ' has no description specified in ' +
                                     'markdown file "' + markdown_filename + '".')

                    markdown_description = markdown_description.replace('\n', ' ')
                    if not markdown_description.startswith(plugin_description):
                        print_notice(args.strict, 'Description of property "' + plugin_property + '" in markdown ' +
                                     'file "' + markdown_filename + '" does not begin with the same description ' +
                                     'found in the config class "' + config_filename + '".')
                        if args.showdiff:
                            print('\t* Plugin:\t' + plugin_description)
                            print('\t* Markdown:\t' + markdown_description)
                            print
                except KeyError:
                    print_notice(args.strict, 'Property "' + plugin_property + '" has no description specified in ' +
                                 'markdown file "' + markdown_filename + '".')
                    continue


def validate(args, plugin_path):
    # Check whether to parse this class
    class_filename = plugin_path[plugin_path.rfind('/') + 1:]
    if class_filename in IGNORED_FILES:
        return

    # Parse the Java file
    tree = parse_file(plugin_path, class_filename)

    # Get class information
    plugin_class_declaration = tree.types[0]
    config_class_declaration = get_config_class(plugin_class_declaration)

    # If no config class is found
    if config_class_declaration is None:
        return

    # If no plugin class is found or the plugin class is abstract
    if plugin_class_declaration is config_class_declaration or is_abstract(plugin_class_declaration):
        return

    # Get plugin and plugin config properties
    plugin_properties = get_plugin_properties(plugin_class_declaration)
    plugin_config_properties = get_plugin_config_properties(config_class_declaration)

    # Parse the markdown file
    markdown_file_path = find_markdown_file(plugin_path, plugin_properties)
    markdown_filename = markdown_file_path[markdown_file_path.rfind('/') + 1:]

    # Print class information
    header = 'Validating ' + plugin_class_declaration.name + ' against ' + markdown_filename
    print('=' * len(header) + '\n' + header + '\n' + '=' * len(header) + '\n')

    markdown_properties = parse_markdown_file(markdown_file_path, markdown_filename, args)

    # If no markdown file was found
    if markdown_properties is None:
        print('Done.')
        print
        return

    # Begin validating properties
    validate_properties_present(class_filename, markdown_filename, plugin_config_properties, markdown_properties, args)
    validate_descriptions_match(class_filename, markdown_filename, plugin_config_properties, markdown_properties, args)

    print('Done.')
    print


def run_validator(args):
    for root_dir, sub_dirs, files in os.walk(args.path):
        for filename in files:
            if filename.endswith('.java'):
                validate(args, root_dir + '/' + filename)


def main():
    args = setup_args()
    run_validator(args)


if __name__ == "__main__":
    main()
