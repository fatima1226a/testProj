"""DRF mode only: JSON parser that answers 400 instead of 500 on pathologically nested bodies."""
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser as BaseJSONParser


class JSONParser(BaseJSONParser):
    def parse(self, stream, media_type=None, parser_context=None):
        try:
            return super().parse(stream, media_type, parser_context)
        except RecursionError as error:
            raise ParseError("JSON parse error - nesting is too deep") from error
