@_default:
    just --list

@lint:
    black .

@update:
    pip install -U -r requirements.in
