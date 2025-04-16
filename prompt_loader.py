import os
from jinja2 import Template

PROMPT_DIR = os.path.join(os.path.dirname(__file__), 'prompts')

def load_prompt(template_name: str) -> str:
    template_path = os.path.join(PROMPT_DIR, template_name)
    with open(template_path, 'r', encoding='utf-8') as file:
        return file.read()

def render_prompt(template_str: str, context: dict) -> str:
    template = Template(template_str)
    return template.render(context)
