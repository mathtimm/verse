from prose.reports.core import LatexTemplate
import jinja2
from os import path

template_folder = path.abspath(path.join(path.dirname(__file__), "..", "..", "latex"))


class VerseLatexTemplate(LatexTemplate):

    def __init__(self, template_name, style='paper'):
        LatexTemplate.__init__(self, style=style)
        self.template_name = template_name
        self.load_template()

    def load_template(self):
        latex_jinja_env = jinja2.Environment(
            block_start_string='\BLOCK{',
            block_end_string='}',
            variable_start_string='\VAR{',
            variable_end_string='}',
            comment_start_string='\#{',
            comment_end_string='}',
            line_statement_prefix='%%',
            line_comment_prefix='%#',
            trim_blocks=True,
            autoescape=False,
            loader=jinja2.FileSystemLoader(template_folder)
        )
        self.template = latex_jinja_env.get_template(self.template_name)