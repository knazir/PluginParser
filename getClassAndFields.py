#!/usr/bin/env python2

import ParserExceptions

import sys
import plyj.parser
import plyj.model as m


def print_imports(tree):
    for import_decl in tree.import_declarations:
        print('import ' + str(import_decl.name.value) + ';')
    print


# Assumed to only contain one outer-level class as per style guide
def get_class_declaration(tree):
    if len(tree.type_declarations) is 0:
        raise ParserExceptions.ClassNotFoundError('Unable to find Java class in ' + sys.argv[1])
    return tree.type_declarations[0]


def get_class_signature(class_decl):
    class_signature = class_decl.name
    if class_decl.extends is not None:
        class_signature += ' extends ' + class_decl.extends.name.value
    if len(class_decl.implements) is not 0:
        class_signature += ' implements ' + ', '.join([type.name.value for type in class_decl.implements])
    return class_signature


def reconstruct_argument(single_member):
    if single_member.__class__.__name__ is 'Literal':
        # strip opening and closing double quotes
        return single_member.value[1:-1]
    elif single_member.__class__.__name__ is not 'Additive':
        return 'UNSUPPORTED ANNOTATION ARGUMENT: ' + single_member.__class__.__name__
    elif single_member.operator is not '+':
        return 'UNSUPPORTED ANNOTATION OPERATOR: ' + single_member.operator
    else:
        return reconstruct_argument(single_member.lhs) + reconstruct_argument(single_member.rhs)


def get_annotation_argument(single_member):
    if single_member is None:
        return ''
    else:
        return '("' + reconstruct_argument(single_member) + '")'


def print_annotations(modifiers):
    for modifier in modifiers:
        if modifier.__class__.__name__ is 'Annotation':
            print('\t@' + modifier.name.value + get_annotation_argument(modifier.single_member))


def print_field_name(field_decl, var_decl):
    if type(field_decl.type) is str:
        type_name = field_decl.type
    else:
        type_name = field_decl.type.name.value
    print('\t' + type_name + ' ' + var_decl.variable.name)


def main():
    # Parse the Java file
    p = plyj.parser.Parser()
    tree = p.parse_file(sys.argv[1])

    # Get class information
    class_decl = get_class_declaration(tree)

    # Print class information
    print_imports(tree)
    print(get_class_signature(class_decl))

    # Print fields
    for field_decl in [decl for decl in class_decl.body if type(decl) is m.FieldDeclaration]:
        for var_decl in field_decl.variable_declarators:
            print_annotations(field_decl.modifiers)
            print_field_name(field_decl, var_decl)
            print

if __name__ == "__main__":
    main()