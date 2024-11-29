from gptpdf import parse_pdf
from gptpdf.parse import _parse_pdf_to_images
from typing import List, Tuple, Optional, Dict
import os
import re
from typing import List, Tuple, Optional, Dict
import logging
import concurrent.futures


DEFAULT_PROMPT = """使用markdown语法，将图片中识别到的文字转换为markdown格式输出。你必须做到：
1. 输出和使用识别到的图片的相同的语言，例如，识别到英语的字段，输出的内容必须是英语。
2. 不要解释和输出无关的文字，直接输出图片中的内容。例如，严禁输出 “以下是我根据图片内容生成的markdown文本：”这样的例子，而是应该直接输出markdown。
3. 内容不要包含在```markdown ```中、段落公式使用 $$ $$ 的形式、行内公式使用 $ $ 的形式、忽略掉长直线、忽略掉页码。
再次强调，不要解释和输出无关的文字，直接输出图片中的内容。
"""
DEFAULT_RECT_PROMPT = """图片中用红色框和名称(%s)标注出了一些区域。如果区域是表格或者图片，使用 ![]() 的形式插入到输出内容中，否则直接输出文字内容。
"""
DEFAULT_ROLE_PROMPT = """你是一个PDF文档解析器，使用markdown和latex语法输出图片的内容。
"""


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
api_key = "yourapikey"


def gpt_parse_images2(
        image_infos: List[Tuple[str, List[str]]],
        prompt_dict: Optional[Dict] = None,
        output_dir: str = './',
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = 'gpt-4o',
        verbose: bool = False,
        gpt_worker: int = 1,
        **args
) -> str:
    """
    Parse images to markdown content.
    """
    from GeneralAgent import Agent

    if isinstance(prompt_dict, dict) and 'prompt' in prompt_dict:
        prompt = prompt_dict['prompt']
        logging.info("prompt is provided, using user prompt.")
    else:
        prompt = DEFAULT_PROMPT
        logging.info("prompt is not provided, using default prompt.")
    if isinstance(prompt_dict, dict) and 'rect_prompt' in prompt_dict:
        rect_prompt = prompt_dict['rect_prompt']
        logging.info("rect_prompt is provided, using user prompt.")
    else:
        rect_prompt = DEFAULT_RECT_PROMPT
        logging.info("rect_prompt is not provided, using default prompt.")
    if isinstance(prompt_dict, dict) and 'role_prompt' in prompt_dict:
        role_prompt = prompt_dict['role_prompt']
        logging.info("role_prompt is provided, using user prompt.")
    else:
        role_prompt = DEFAULT_ROLE_PROMPT
        logging.info("role_prompt is not provided, using default prompt.")

    def _process_page(index: int, image_info: Tuple[str, List[str]]) -> Tuple[int, str]:
        logging.info(f'gpt parse page: {index}')
        agent = Agent(role=role_prompt, api_key=api_key, base_url=base_url, disable_python_run=True, model=model, **args)
        page_image, rect_images = image_info
        local_prompt = prompt
        if rect_images:
            local_prompt += rect_prompt + ', '.join(rect_images)
        content = agent.run([local_prompt, {'image': page_image}], display=verbose)
        return index, content

    contents = [None] * len(image_infos)  # length = number of pages
    with concurrent.futures.ThreadPoolExecutor(max_workers=gpt_worker) as executor:
        # index -> 页数
        futures = [executor.submit(_process_page, index, image_info) for index, image_info in enumerate(image_infos)]

        for future in concurrent.futures.as_completed(futures):
            index, content = future.result()

            # 在某些情况下大模型还是会输出 ```markdown ```字符串
            if '```markdown' in content:
                content = content.replace('```markdown\n', '')
                last_backticks_pos = content.rfind('```')
                if last_backticks_pos != -1:
                    content = content[:last_backticks_pos] + content[last_backticks_pos + 3:]
            page_annotation = '\nPAGE_INDEX-' + str(index) + '\n'  # 在这里加上页数
            contents[index] = page_annotation + content

    output_path = os.path.join(output_dir, 'output.md')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(contents))

    return '\n\n'.join(contents)


def parse_pdf2(pdf_path: str,
        output_dir: str = './',
        prompt: Optional[Dict] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = 'gpt-4o',
        verbose: bool = False,
        gpt_worker: int = 1,
        **args
) -> Tuple[str, List[str]]:

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # List[Tuple[str, List[str]]]: (page_image, rect_images)
    # page_image: {page_index}.png; rect_image: {page_index}_{index}.png
    image_infos = _parse_pdf_to_images(pdf_path, output_dir=output_dir)

    content = gpt_parse_images2(
        image_infos=image_infos,
        output_dir=output_dir,
        prompt_dict=prompt,
        api_key=api_key,
        base_url=base_url,
        model=model,
        verbose=verbose,
        gpt_worker=gpt_worker,
        **args
    )

    all_rect_images = []
    # remove all rect images
    if not verbose:
        for page_image, rect_images in image_infos:
            if os.path.exists(page_image):
                os.remove(page_image)
            all_rect_images.extend(rect_images)
    return content, all_rect_images


def main():
    parent_directory = 'heg_esg_reports'
    for file_name in os.listdir(parent_directory):
        file_path = os.path.join(parent_directory, file_name)
        print(file_path)
        if os.path.isfile(file_path):
            output_dir = "parsed_output_with_page_index/" + file_name.replace('.pdf', '') + '结果'
            content, image_paths = parse_pdf2(file_path, api_key=api_key, output_dir=output_dir,
                                              model='gpt-4o-mini', gpt_worker=4)

            print(content)
            print('---------------------- SEPERATOR --------------------------')
            print(image_paths)


if __name__ == '__main__':
    main()