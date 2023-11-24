
## Instrument all your Circle CI projects in bulk for DataDog CI Visibility

This repository contains a script that allows you to configure all your Circle CI projects for DataDog CI Visibiliy.

You may also configure each project manually using the steps provided in the DataDog [documentation](https://docs.datadoghq.com/continuous_integration/pipelines/circleci/).

### What you'll need

Before executing the script, you will need the following:

- A DataDog api key, which you can obtain from the [DataDog app](https://app.datadoghq.com/organization-settings/api-keys).
- A CircleCI personal API token, which you can create inside [User Settings](https://app.circleci.com/settings/user/tokens) within Circle CI.

**Note:** Circle CI project API tokens are not valid, please create a personal API token.

### How it works

First, you must log in to Circle CI and follow all the projects that you want to configure for DataDog CI Visibility.

If you want to configure all projects in a Circle CI organization, you may click the "Follow All" button located at the top of the page.

Lastly, you may execute the script. You will need python3 and the requests package.

```bash
python3 service_hooks.py \
    --dd-api-key ******************** \
    --circle-token ********************** \
    --threads 4
```

For more information, use `pyhon3 service_hooks.py --help`.

### Useful resources
- [Datadog documentation](https://docs.datadoghq.com/continuous_integration/pipelines/circleci/)
- [What is Datadog CI Visibility?](https://www.datadoghq.com/blog/datadog-ci-visibility/)

