import re
import os
import markdown
import json
import openai
from langchain_text_splitters import RecursiveCharacterTextSplitter

api_key = "yourapikey"
openai.api_key = api_key



CONSTRUCT_JSON_TABLE_PROMPT = """
    ### INSTRUCTION ###
    You are a helpful AI accountant who bookkeeps and collects data extracted from markdown table. Your job lies in interpreting the markdown tables parsed from selected companies’ ESG reports in pdf format and converting it into JSON formatted table, given the description or context if provided to you. You have to follow these steps:
    1. Read through the context (some context may be irrelevant, you can decide to discard it) and the entire table, understand its structure and what it is for. The context is extracted from the report, it denotes the last 4 lines and the next 2 lines of where the table is in the page. Most of the markdown tables are in good shape but few are corrupted and may have rows misplaced during the parsing process. For the corrupted tables, if context has given you enough information, you may fill out the missing part, only if you are really sure! Again, you should be mindful of it and use the context to help you interpret the table. 
    2. You should identify the header In the table, so you can construct the key fields for each row. If there is no header in the table, represent each row of data in list form. 
    3. If the table itself is malformed, for example, contain different headers, or represent data differently, interpret it wisely with your understanding. ONLY ONE RULE IS TO STORE THEM UNDER THE 'data' field.
    4. The JSON formatted table should only contain data field, that represents row data only. Replace empty or field noted as '-'  with 'null' value. You will also be given the page index, just put it as a separated field.
    5. Some tables might contain meta information like unit or notes, you should put it in meta data field.
    
    ### DATA ###
    The context of the table is {context}.
    The original markdown table is {markdown_table}.
    The page position, noted as index, of the markdown table in the original file is {page_index}.
    
    IMPORTANT: You should preserve data integrity (including respecting the language preference in the markdown table) as you generate the JSON formatted table and NOT make up any data in the table.
    
    ### OUTPUT ###
    Do not output any other languages other than the JSON formatted table. Store all non-metadata fields into 'data' field. Remember to put page index given to you in the output!
    
    ### EXAMPLES ###
    TABLE WITH HEADER:
    {{
    "page_index": page_index,
    "data": [
    {{
    header[1]: first_row_data[1],
    header[2]: first_row_data[2],
    …,
    header[n]: first_row_data[n]
    }},
    {{
    header[1]: second_row_data[1],
    header[2]: second_row_data[2],
    …,
    header[n]: second_row_data[n]
    }},
    ….,
    {{
    header[1]: n_th_row_data[1],
    header[2]: n_th_row_data[2],
    …,
    header[n]: n_th_row_data[n]
    }}
    ]
    }}
    
    TABLES WITHOUT HEADER:
    {{
    "page_index": page_index,
    "data": [ 
    [
    first_row_data[1], first_row_data[2], …, first_row_data[n]
    ],
    [ 
    second_row_data[1], second_row_data[2], …, second_row_data[n]
    ],
    ….,
    [
    n_th_row_data[1], n_th_row_data[2],…, n_th_row_data[n]
    ]
    ]
    }}
    
    TABLES WITH METADATA FIELD:
    {{
    "metadata" : {{
    first_metadata_name_in_markdown_table: first_value_in_markdown_table,
    second_metadata_name_in_markdown_table: second_value_in_markdown_table,
    ….
    n_th_metadata_name_in_markdown_table: n_th_value_in_markdown_table,
    }},
    "page_index": page_index,
    "data": [
    {{
    header[1]: first_row_data[1],
    header[2]: first_row_data[2],
    …,
    header[n]: first_row_data[n]
    }},
    {{
    header[1]: second_row_data[1],
    header[2]: second_row_data[2],
    …,
    header[n]: second_row_data[n]
    }},
    …,
    {{
    header[1]: n_th_row_data[1],
    header[2]: n_th_row_data[2],
    …,
    header[n]: n_th_row_data[n]
    }}
    ]
    }}
    """


def generate_json_table(description='', table='', page_index=0):
    completion = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": CONSTRUCT_JSON_TABLE_PROMPT.format(markdown_table=table, context=description, page_index=page_index)
            }
            ],
         )
    res = completion.choices[0].message.content.strip()
    return res


def process_tables(position_dict, position_list, tables):
    markdown_tables = {}
    # start processing table
    for label, table in tables.items():
        table_str = '\n'.join(table['table'])
        context = ''  # get the context of the table
        if label in position_dict:
            index = position_dict[label]
            start = max(0, index - 4)  # 避免开头和结尾在文件的首尾
            end = min(len(position_list), index + 2)
            context = '\n'.join(position_list[start:end])
        # print(context)
        # print('-------------------------- SEPERATOR -----------------------------')
        result = generate_json_table(description=context, table=table_str, page_index=table['page_index'])
        try:
            json_data = json.loads(result)
            markdown_tables[label] = json_data
        except json.JSONDecodeError as e:
            markdown_tables[label] = result
    return markdown_tables


def extract_markdown_table_with_re(text):
    # Split the input into lines
    lines = text.split("\n")
    # remove all newlines
    lines = [line.strip() for line in lines if line.strip()]

    position_list = []
    new_contents = []
    all_tables = {}
    table_index = 0
    md_table = []

    for index, line in enumerate(lines):
        if re.match(r"^PAGE_INDEX-", line):
            new_contents.append(line)
            page_index = int(line.split('-')[1])
            continue
        if not re.search(r"\|+", line):
            new_contents.append(line)  # non-table texts
            position_list.append(line)  # all element, store their position (including table position - identified with markdown_table[index])

        else:  # line contains |
            md_table.append(line)
            # Edge case, last line of the content
            if (index == len(lines) - 1) or (not re.search(r"\|+", lines[index+1]) and not re.search(r"\|+", lines[index+2])):  # the next two lines after it does not contain |
                all_tables['markdown_tables[' + str(table_index) + ']'] = {'page_index': page_index, 'table': md_table}
                # new_contents.append('markdown_tables[' + str(table_index) + ']')

                # store in position_list for the whole table content
                position_list.append('markdown_tables[' + str(table_index) + ']')
                # reinitialize the table and extract the next table
                table_index += 1
                md_table = []

    return position_list, new_contents, all_tables


def resplit(seg, max_length=1500):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_length,
        separators=[
            "\n",
            "\u3002",
            "PAGE_INDEX -",
            " "],
        is_separator_regex=False)

    if len(seg) > max_length:
        sub_segment = text_splitter.split_text(seg)
        return sub_segment
    else:
        return seg


def split_header(text_list, pattern, index_pattern, level=1, page_ind=0):
    result_dict = {}
    last_ind = page_ind
    last_match = None
    for i, line in enumerate(text_list):
        # Search, allocate, and update the FIRST page index to the first header
        if re.match(index_pattern, line):
            page_ind = int(line.split('-')[1])

        if re.match(pattern, line):
            if last_match is None and i != 0:  # EDGE CASE: check for content before the first match pattern
                extracted_text_list = resplit(text_list[:i]) if level == 2 else text_list[:i]
                result_dict[f'SPLIT AT LEVEL {level}, PAGE_{last_ind}'] = {'page_index': last_ind, 'text': extracted_text_list}
            elif last_match is None and i == 0:
                pass
            else:
                extracted_text_list = resplit(text_list[last_match + 1: i]) if level == 2 else text_list[last_match + 1:i]
                result_dict[text_list[last_match] + ' _' + str(last_ind)] = {'page_index': last_ind, 'text': extracted_text_list}
            last_match = i
            last_ind = page_ind

        if i == len(text_list) - 1:  # deal with the very last match
            if last_match is None:  # if no match at all in the whole text,  return the whole list intact
                if level == 2:
                    return text_list
                return {f'ALL CONTENT AT LEVEL {level}': {'page_index': last_ind, 'text': text_list}}
            else:
                if last_match == i:  # Edge case last_match is at the end
                    extracted_text_list = resplit(text_list[i]) if level == 2 else text_list[i]
                else:
                    extracted_text_list = resplit(text_list[last_match + 1:]) if level == 2 else text_list[last_match + 1: ]
                result_dict[text_list[last_match] + ' _' + str(last_ind)] = {'page_index': last_ind, 'text': extracted_text_list}

    return result_dict


def split_text(text_list):
    page_index_pattern = r"^PAGE_INDEX-"
    level_1_pattern = r'^# .*'
    level_2_pattern = r'^## .*'
    level_1_dict = split_header(text_list=text_list, pattern=level_1_pattern, index_pattern=page_index_pattern)
    # split based on the second header for every first header segment

    for header, content in level_1_dict.items():
        segment = content['text']
        page_index = content['page_index']
        # count += len([i for i in segment if re.match(level_2_pattern, i)])
        level_2_segment = split_header(text_list=segment, pattern=level_2_pattern, index_pattern=page_index_pattern, page_ind=page_index, level=2)
        if isinstance(level_2_segment, list):  # no second level header match, chunk based on length
            level_2_segment = resplit(level_2_segment)
        level_1_dict[header]['text'] = level_2_segment

    return level_1_dict


def main():
    output = 'parsed_output_with_page_index/2023年度报表结果/output.md'
    with open(output, 'r', encoding='utf-8') as file:
             content = file.read()

    line_position_list, new_contents, unprocessed_tables = extract_markdown_table_with_re(content)
    line_position_dict = {value: index for index, value in enumerate(line_position_list)}
    ### new_contents: 按照页码来存储/仍保留页码信息
    ### line_position_list:按照每一行的内容来存储

    # print('-------------------------- SEPERATOR -----------------------------')
    # for index, table in unprocessed_tables.items():
    #     print('-------------------------- ', index, ' -----------------------------')
    #     print()
    #     print('\n'.join(table))
    #     print()

    # table position, table context, table content, page_index
    # PROCESS TABLES
    # markdown_tables = process_tables(line_position_dict, line_position_list, unprocessed_tables)

    # for label, table in markdown_tables.items():
    #     print('-------------------------- ', label, ' -----------------------------')
    #     print()
    #     print(table)
    #     print()
        # table position, table context, table content, page_index

    # PROCESS CONTEXT: CHUNK THE TEXT
    text_result = split_text(new_contents)
    for key, value in text_result.items():
        print(key)
        print(value)
        print()



if __name__ == '__main__':
    main()