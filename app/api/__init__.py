"""HTTP API layer.

Routes are thin: they validate input, call services, and shape responses.
No route contains a security decision. Every security decision lives in
`app.ice.controller`.
"""