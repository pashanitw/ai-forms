from fasthtml.common import *
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional
from openai import OpenAI
from textwrap import dedent
from dotenv import load_dotenv

load_dotenv()
MODEL = "gpt-4o-2024-08-06"
client = OpenAI()

# App with custom styling to override the pico defaults
css = Style(":root { --pico-font-size: 100%; --pico-font-family: Pacifico, cursive;}")
app = FastHTML(hdrs=(picolink, css))

rt = app.route


class TypeEnum(str, Enum):
    text = "text"
    number = "number"
    date = "date"
    radio = "radio"
    checkbox = "checkbox"
    select = "select"
    textarea = "textarea"


class Options(BaseModel):
    label: str = Field(description="unique label for the option")
    value: str = Field(description="unique value for the option")


class FormField(BaseModel):
    label: str = Field(description="Title of the field")
    type: TypeEnum = Field(description="Type of the field")
    name: str = Field(description="unique name to access the field")
    required: bool = Field(description="Whether the field is required")
    placeholder: Optional[str] = Field(
        description="Placeholder for the field. only applicable for the type text and text area"
    )
    options: Optional[List[Options]] = Field(
        description="Options for the field. only applicable for the type radio, checkbox and select"
    )


class DynamicForm(BaseModel):
    title: str = Field(description="Title of the form")
    fields: List[FormField] = Field(description="List of fields")


form_prompt = ""
dynamic_form_data: DynamicForm = None


def get_form_response(prompt):
    system_prompt = """
        You are a helpful dynamic html form creator. You will be provided with a dynamic form requirement,
        and your goal will be to output form fields.
        For each field, just provide the correct configuration.
    """
    completion = client.beta.chat.completions.parse(
        model=MODEL,
        messages=[
            {"role": "system", "content": dedent(system_prompt)},
            {"role": "user", "content": prompt},
        ],
        response_format=DynamicForm,
    )

    return completion.choices[0].message


def create_dynamic_form(form_data: DynamicForm | None):
    if dynamic_form_data is None:
        return None

    fields = []

    for field in form_data.fields:
        field_type = field.type
        if field_type in ["text", "number", "date"]:
            fields.append(
                Div(
                    Label(field.label, _for=field.name),
                    Input(
                        type=field_type,
                        name=field.name,
                        placeholder=field.placeholder,
                        required=field.required,
                    ),
                    style="margin-bottom: 15px;",
                )
            )
        elif field_type == "select":
            options = [
                Option(value=opt.value, label=opt.label) for opt in field.options
            ]
            fields.append(
                Div(
                    Label(field.label, _for=field.label),
                    Select(*options, name=field.name, required=field.required),
                    style="margin-bottom: 15px;",
                )
            )
        elif field_type == "checkbox":
            checkboxes = [
                Div(
                    Input(
                        type="checkbox",
                        name=field.name,
                        value=opt.value,
                        id=f"{field.name}_{opt.value}",
                    ),
                    Label(opt.label, _for=f"{field.name}_{opt.value}"),
                )
                for opt in field.options
            ]
            fields.append(
                Div(Label(field.label), Div(*checkboxes), style="margin-bottom: 15px;")
            )
        elif field_type == "radio":
            radios = [
                Div(
                    Input(
                        type="radio",
                        name=field.name,
                        value=opt.value,
                        id=f"{field.name}_{opt.value}",
                        required=field.required,
                    ),
                    Label(opt.label, _for=f"{field.name}_{opt.label}"),
                )
                for opt in field.options
            ]
            fields.append(
                Div(Label(field.label), Div(*radios), style="margin-bottom: 15px;")
            )
        elif field_type == "textarea":
            fields.append(
                Div(
                    Label(field.label, _for=field.name),
                    Textarea(
                        name=field.name,
                        placeholder=field.placeholder,
                        required=field.required,
                    ),
                    style="margin-bottom: 15px;",
                )
            )

    form = Form(
        *fields,
        Button("Submit", type="submit", style="margin-top: 20px;"),
        method="post",
        action="/submit",
    )

    return Container(H1(form_data.title), form)


@app.get("/")
def get():
    prompt_area = Form(
        H2("Enter your prompt here to create a dynamic form"),
        Textarea(
            name="prompt",
            placeholder="Enter your prompt...",
            style="width: 100%; margin-bottom: 5px;",
            id="form_prompt",
        )(form_prompt),
        Button(
            "Create Form",
            type="button",  # Ensure it's a button, not submit
            id="create_form_button",
            style="margin-top: 15px;",
            hx_post="/update-prompt",
            hx_trigger="click",
            hx_target="#form_area",
            hx_swap="innerHTML",
            onclick="document.getElementById('form_area').innerHTML = 'Loading...';",
        ),
    )

    form_area = Div(id="form_area")

    return Container(prompt_area, form_area)


@app.post("/update-prompt")
async def update_prompt(request):
    global form_prompt, dynamic_form_data
    form_data = await request.form()
    form_prompt = form_data.get("prompt", form_prompt)
    print(f"Updated Prompt: {form_prompt}")
    if form_prompt:
        dynamic_form_data = get_form_response(form_prompt)
        return Div(create_dynamic_form(dynamic_form_data.parsed), id="form_area")

    # Fallback in case of issues
    return Div("Error generating form. Please try again.", id="form_area")


serve()
