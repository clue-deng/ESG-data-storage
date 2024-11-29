import uuid
import os
from parse_markdown_table import extract_markdown_table_with_re, process_tables, split_text

def text_to_csv():
    pass

def main():
    parent_directory = "parsed_output_with_page_index"
    output_directory = "csv_output"

    for file_name in os.listdir(parent_directory):
        file_path = os.path.join(parent_directory, file_name) + '/output.md'
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()

        line_position_list, new_contents, unprocessed_tables = extract_markdown_table_with_re(content)
        line_position_dict = {value: index for index, value in enumerate(line_position_list)}
        markdown_tables = process_tables(line_position_dict, line_position_list, unprocessed_tables)

        for ind, table in enumerate(markdown_tables.items()):
            output_dir = os.path.join(output_directory, file_name)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            output_path = os.path.join(output_dir, 'tables' + str(ind) +'.csv')
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(table)



main()
