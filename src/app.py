import json
import os

from flask import Flask, render_template, request, redirect, url_for, send_from_directory, jsonify

from .bootstrap import get_or_create_app
from . import callback_handler
from . import routes_handler
from .models import db, RouteModel, CallbackModel


app = get_or_create_app()


@app.route("/")
def hp():
    return render_template('index.html')


@app.route("/robots.txt")
def robots():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'robots.txt', mimetype='text/plain')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/x-icon')


@app.route("/new")
def new():
    # Cleanup old routes
    routes_handler.cleanup_old_routes()

    # Generate a new route
    new_route = routes_handler.new()

    return redirect('/' + new_route + '/inspect'), 307


@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def catch_all(path):
    # Get route
    route_path = path

    # If we are inspecting a route
    inspect = route_path.rfind('/inspect')
    if inspect > 0:
        inspect_json = True if route_path.rfind('/inspect/json') > 0 else False
        route_path = route_path[:inspect]

    # Lookup route
    route = RouteModel.query.filter_by(route=route_path).first()

    # Return 404 if unknown route
    if not route:
        return redirect(url_for('abort_404')), 307

    if inspect > 0:
        # Load callbacks
        callbacks = CallbackModel.query.filter_by(
            route_id=route.id).order_by(CallbackModel.id.desc()).all()

        # Process rows
        callbacks_processed = []
        for callback in callbacks:
            # Prepare body
            body = {
                'data': callback.body if callback.body else None,
                'size': len(callback.body) if callback.body else 0
            }
            if body['data'] and callback_handler.is_json(body['data']):
                body['data'] = json.loads(body['data'])

            # Prepare args
            args = None
            if callback.args:
                args = json.loads(callback.args)

            callbacks_processed.append(
                {
                    'headers': json.loads(callback.headers),
                    'method': callback.method,
                    'args': args,
                    'body': body,
                    'date': callback.date,
                    'referrer': callback.referrer,
                    'remote_addr': callback.remote_addr
                }
            )

        if inspect_json:  # Json format
            return jsonify({
                'routes': {
                    'inspect': {
                        'html': request.host_url + route_path + '/inspect',
                        'json': request.host_url + route_path + '/inspect/json'
                    },
                    'webhook': request.host_url + route_path
                },
                'callbacks': callbacks_processed,
                'creation_date': route.creation_date
            })
        else:  # HTML rendering
            return render_template(
                'inspect.html',
                route_path=route_path,
                callbacks=callbacks_processed,
                host_url=request.host_url
            )
    else:
        # Save callback
        callback_handler.save(route.id)

        return 'OK'


@app.route("/404")
def abort_404():
    return render_template('404.html'), 404
