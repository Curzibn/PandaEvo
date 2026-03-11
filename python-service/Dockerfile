FROM pandaevo-base

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml .
RUN python -c "import tomllib; deps=tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; open('requirements.txt','w').write('\n'.join(deps))" \
    && uv pip install --system -r requirements.txt

COPY . .

EXPOSE 10600
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10600"]
