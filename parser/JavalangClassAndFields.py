#!/usr/bin/env python2

import ParserExceptions
import sys
import javalang


def parse_file():
    with open(sys.argv[1], 'r') as java_file:
        file_contents = java_file.read()
    tree = javalang.parse.parse(file_contents)
    if len(tree.types) is 0:
        raise ParserExceptions.ClassNotFoundException('Unable to find Java class in ' + sys.argv[1])
    return tree


def get_class_signature(class_decl):
    class_signature = class_decl.name;
    if class_decl.extends is not None:
        class_signature += ' extends ' + class_decl.extends.name;
    if class_decl.implements is not None:
        class_signature += ' implements ' + ', '.join([interface.name for interface in class_decl.implements])
    return class_signature


def reconstruct_argument(argument_piece):
    if argument_piece.__class__.__name__ is 'Literal':
        #strip opening and closing double quotes
        return argument_piece.value[1:-1]
    elif argument_piece.__class__.__name__ is not 'BinaryOperation':
        return 'UNSUPPORTED ANNOTATION OPERATION: ' + argument_piece.__class__.__name__
    else:
        return reconstruct_argument(argument_piece.operandl) + reconstruct_argument(argument_piece.operandr)


def get_annotation_argument(children):
    if children[1] is None:
        return ''
    else:
        return '("' + reconstruct_argument(children[1]) + '")'  # children[1] is the first argument


def get_field_name(field_decl):
    field_string = ' '.join([modifier for modifier in field_decl.modifiers]) + ' '
    field_string += field_decl.type.name + ' ' + field_decl.declarators[0].name
    return field_string


def main():
    # Parse the Java file
    tree = parse_file()

    # Get class information
    class_decl = tree.types[0]

    # Print class information
    print(get_class_signature(class_decl))
    print

    # Print fields
    for field_decl in class_decl.fields:
        for annotation in field_decl.annotations:
            print('\t@' + annotation.name + get_annotation_argument(annotation.children))
        print('\t' + get_field_name(field_decl))
        print

if __name__ == "__main__":
    main()