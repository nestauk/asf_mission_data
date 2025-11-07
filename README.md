# asf_mission_data

## Setup

This project uses [`uv`](https://docs.astral.sh/uv/) for virtual environment management. If you are new to `uv`, you can find the [quickstart guide here](https://docs.astral.sh/uv/getting-started/).

We also utilise `direnv` via the `.envrc` file to automatically:

- Import your environment variables from `.env`
- Activate your virtual environment (_only if you comment out the relevant lines in `.envrc`_)

After installing `direnv` and `uv` on your system (we recommend doing this via [`brew`](https://brew.sh/) on macOS), you **must** run the following commands in your terminal to set up the project:

```bash
direnv allow
uv sync
uv run pre-commit install --install-hooks
```

## Setup Airflow in Docker for Local Development

Following the [airflow docker guidance](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html), pull the Dockerfile and docker compose from the repo.

Create a .env file with the following structure:

> export AIRFLOW_PROJ_DIR="~/projects/asf_mission_data/asf_mission_data"
> export AWS_ACCESS_KEY_ID="\<my id>"
> export AWS_SECRET_ACCESS_KEY="\<my secret key>"
> export AWS_DEFAULT_REGION="\<my region>"
> export AIRFLOW_UID=\$(id -u)
> export AIRFLOW_GID=0
> \# Some email env vars
> export EMAIL_IAM="\<my email iam>"
> export EMAIL_SMTP_USER="\<my user>"
> export EMAIL_SMTP_PASSWORD="\<my password>"
> export AIRFLOW**API_AUTH**JWT_SECRET="\<my jwt secret>"

Run the following commands:

`docker compose run airflow-cli airflow config list`

Note that the above initialises airflow.cfg and may not be necessary.

Run the database migrations:
`docker compose up airflow-init`

Start all services:
`docker compose up`

You should now be able to access airflow at localhost on port 8080.

## Contributor guidelines

[Technical and working style guidelines](https://github.com/nestauk/ds-cookiecutter/blob/master/GUIDELINES.md)

---

<small><p>Project based on <a target="_blank" href="https://github.com/nestauk/ds-cookiecutter">Nesta's data science project template</a>
(<a href="http://nestauk.github.io/ds-cookiecutter">Read the docs here</a>).
</small>
