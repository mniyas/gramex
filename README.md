Gramex 1.0
================================================================================

Gramex 1.0 is a backward-incompatible re-boot of the visualisation platform.

- *Why 1.0?* We use semantic versioning. `1.0` means we have a published API that
  we follow.
- *Why backward-incompatible?* There are many bad practices that Gramex 0.x
  encourages that we want to break-away from. For example, inconsistent
  attributes in chart components.

This is the work-in-progress design.

Principles
--------------------------------------------------------------------------------

These are the core principles of Gramex.

1. **Data, not code** We modify data to change the functionality of the
   application, wherever posssible. Code is written only as a last resort,
   either to provide very niche (and rare) functionality, or to cover a large
   number of general-purpose cases.
1. **Modular licensing**. It can be broken down into smaller parts that can be
   licensed independently, with customisable trials.

These are proposed principles, for discussion.

1. **User-friendly* at every stage. Move from code to data. From data to GUI.
   From GUI to live editing.
1. **Lazy computations**. Defer computation to as late as possible.
1. **Modular**. Its parts can be used independently. It can use third party
   modules easily.
1. **Automated reloads**. Configurations are reloaded transparently.
1. **RESTful**. Use REST APIs and friendly URLs.
1. **YAML** for configuration, not XML (too verbose), or JSON (too strict, no
   comments).

Architecture
--------------------------------------------------------------------------------

Gramex has:

- **A core server**, which provides a variety of services (via Python libraries)
  to the entire application.
- **Handlers**, which handle specific URL patterns as required. They may show
  templates, act as a websocket, provide a data interface, serve static files,
  etc.
- **Components**, which can be used by handlers to render certain kinds of
  outputs.

Server
--------------------------------------------------------------------------------

The server is the core I/O engine. It translates requests into responses and
provides a set of services.

The server is asynchronous. It executes on an event loop. Handlers can use
asynchronous functionality (e.g. deferred execution).

The server is configured by a default `gramex.yaml`. Gramex runs in a home
directory, which can have a `gramex.yaml` that overrides it. It has the
following structure:

    - app:
        app-keys: app-values
    - urls:
        url-mapper Configuration parameters
    - service 1:
        service 1 configuration parameters
    - service 2:
        service 2 configuration parameters
    - ...

The server runs a separate thread(s) that do the following:

- Interrupt long requests, even without the consent of the app. (For example, if
  the connection closes, just stop the function.)
- Re-load changed config files into memory
- Deferred logging
- etc.

- Will we allow new event loops on threads for handlers?

The server provides an admin view that allows admins to see (and perhaps
modify?) the configuration.


### URL Mapping

The `urls` configuration maps a URL pattern to a handler. For example:

      - url: /secc/.*                       # All URLs beginning with /secc/
        handler: TemplateHandler            # Handles templates
        name: SECC                          # An unique name for this handler
        path: d:/secc/                      # Path option passed to handler
      - url: /data
        handler: DataAPIHandler
      - url: /auth
        handler: SAMLHandler
      - url: /oauth
        handler: OAuthHandler
      - url: /log
        handler: GoogleAnalyticsLikeHandler
      - url: /websocket
        handler: WebSocketHandler

The `app` configuration allows more URL specs as YAML files. For example:

    app:
      - urls: */gramex.conf.yaml              # Any gramex.conf.yaml under this
                                              # folder's first-level sub-folder
      - urls: d:/novartis/gramex.conf.yaml    # A specific gramex.conf.yaml file

These files are monitored and loaded under the `urls` section in the order
specified.

### Services

- **Namespaced app folders**.
    - Reserved namespaces
    - Add a directory `app/`, and the URL mappings for `/app/...` will be taken
      from the `app/` directory.
    - With `/app/` there is full flexibility on how to handle the URLs
    - No URLs outside `/app/` will be affected.
    - Configurations use data, not code. (e.g. YAML, not Python)
- **Modern protocols** are supported out of box.
    - HTTP, by default
    - HTTPS native support
    - Websocket
    - HTTP/2.0 a.k.a. SPDY
- **Caching**
    - Output follows HTTP caching policy. Server acts as a caching HTTP proxy.
- **Logging** mechanism common across apps
    - Single global logger, modified to accept `app` as a parameter
    - Configured to store / transmit logs as and how required
    - Timing each request, and a generic timer for use within applications
- **Licensing**
    - Will each app have its license? Or is it at a Gramex level?
- **Scheduler**
- **Error handling**
- **Keeping configs up to date**

Externals:

- **Distributed computing** is handled by the apps themselves. This can be via
  an external computing engine (e.g. Spark) or one that is custom-built.
- **Load balancing** is handled by a front-end balancer (e.g. nginx).

References:

- [Ben Darnell's template plans for Tornado 4.1](https://groups.google.com/forum/?fromgroups#!searchin/python-tornado/template$20asynchronous%7Csort:date/python-tornado/Eoyb2wphJ-o/fj9EAb166PIJ)
- [`asynchronous` directive pull request](https://github.com/tornadoweb/tornado/pull/553)
- [`coroutine=` parameter pull request](https://github.com/tornadoweb/tornado/pull/1311)


Services
--------------------------------------------------------------------------------

Services are offered to all apps, which may expose them with or without changes.

- **Rendering** components to PDF, PPTX, PNG, SVG, etc.
- **Caching**
    - Any structure can be cached and re-used across apps
    - Any structure can be uniquely identified, possibly served as a URL
    - Cache management, expiry, re-creation
- **Computation workflow**.
- **Data store**. Perhaps using an API like
  [Webstore](http://webstore.readthedocs.org/en/latest/index.html)
- **Security**
    - Apps can pick an auth mechanism (OAuth, SAML, LDAP, etc.)
    - An app can be an auth provided. By default, a `/admin/` app can provide
      uer management functionality
    - Users have roles. Apps expose a `function(user, roles, request)` to the
      server that determines the rejection, type of rejection, error message,
      log message, etc.
    - Apps can internally further limit access based on role (e.g. only admins
      can see all rows.)
- **Communication**. Emails, etc
- **Uploads**
- **Queues**: If dataframes have to be stored, for example, and we want to avoid
  too many dataframes being stored. Or if we need a cache with a limited memory
  usage.

Components
--------------------------------------------------------------------------------

- Grammar of Graphics
- Consistent rendering principles
- Scaling and other transformations
- Axes
- Colour contrast
- Default stroke colour, stroke width, padding, etc
- Attribute lambda parameters
- Transformable. Transforms should also be composable.
- Ability to access template intermediate variables (layouts, scales, etc) from outside
- Rendering may be on the client side or the server side

Others
--------------------------------------------------------------------------------

- Sample datasets
- App store for apps and data

Contributing
--------------------------------------------------------------------------------

- To **suggest a feature** or **ask a question**, raise an
  [issue](http://code.gramener.com/s.anand/gramex/issues).
- To **comment on a line**, find the
  [commit](http://code.gramener.com/s.anand/gramex/blame/master/README.md) for
  the line and add a comment.
- To **follow changes**, ask @s.anand to add you as a reporter to this project.
- For anything else, raise an
  [issue](http://code.gramener.com/s.anand/gramex/issues).

Thoughts
--------------------------------------------------------------------------------
- How will be incorporate PowerPoint Smart-Art-like infographic layouts?
  - Can we make these infographics without any coding? Bret Victor like?
  - Concepts:
    - Layouts (pack in a shape, grow from a point, stack in a grid)
    - Renderings (shape, photo, size/color/other attributes)
    - Narratives
- How will we incorporate dynamic interactive controls?
- How will we incorporate autolysis?
- Voice / video rendering

Thoughts on interactivity
--------------------------------------------------------------------------------

There are 3 things:

1. Events / components (brushing, clicking, sliding, etc)
2. Actions (filter, zoom-in, etc)
3. Combinations (click-to-filter, etc)

We don't have a catalogue of any of these

Discussion notes
--------------------------------------------------------------------------------

- **Will we have multiple instances of Gramex sharing the same memory?** No.
  This is difficult to implement in Python. Intsead, it will be delegated to
  external engines (databases, Spark, etc.)
- **Will we shift to PyPy?** No. Most libraries (such as database drivers, lxml,
  etc.) do not yet work on PyPy.
