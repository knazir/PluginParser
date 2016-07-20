#!/usr/bin/env python2

import sys
import plyj.parser
import plyj.model as m

# parse the java file
p = plyj.parser.Parser()
tree = p.parse_file(sys.argv[1])
print

# print all imports
for import_decl in tree.import_declarations:
    print('import ' + str(import_decl.name.value) + ';')
print

# get class declaration (assumed to be only outer-level class as per style-guide)
class_decl = tree.type_declarations[0]

# print class signature
class_signature = class_decl.name;
if class_decl.extends is not None:
    class_signature += ' extends ' + class_decl.extends.name.value
if len(class_decl.implements) is not 0:
    class_signature += ' implements ' + ', '.join([type.name.value for type in class_decl.implements])
print(class_signature)

# print fields
for field_decl in [decl for decl in class_decl.body if type(decl) is m.FieldDeclaration]:
    for var_decl in field_decl.variable_declarators:
        #print annotations
        for modifier in field_decl.modifiers:
            if modifier.__class__.__name__ is 'Annotation':
                print('\t@' + modifier.name.value)

        #print field name
        if type(field_decl.type) is str:
            type_name = field_decl.type
        else:
            type_name = field_decl.type.name.value
        print('\t' + type_name + ' ' + var_decl.variable.name)
        print