from flask.ext.classy import FlaskView, route
from flaskext.bcrypt import check_password_hash 
from flask import send_file, render_template, abort, request, Response, g
import os

from ..files import extension, VIDEO_EXTENSIONS, LOOP_EXTENSIONS, AUTOPLAY_EXTENSIONS, get_mimetype, delete_file, processing_status
from ..database import r, _k
from ..config import _cfg
from ..objects import File
from ..network import get_ip

class MediaView(FlaskView):
    route_base = '/'

    @route("/<id>/download")
    def download(self, id):
        f = File.from_hash(id)
        if os.path.exists(os.path.join(_cfg("storage_folder"), f.original)):
           path = os.path.join(_cfg("storage_folder"), f.original)
           return send_file(path, as_attachment=True)
        return self.get(id)

    def _template_params(self, id): 
        f = File.from_hash(id) 
        if not f.original:
            abort(404)

        if f.compression:
            compression = int(float(f.compression) * 100)
        if compression == 100 or processing_status(f.hash) != "done":
            compression = None

        can_delete = None
        if request.cookies.get('hist-opt-out', '0') == '1':
            can_delete = check_password_hash(f.ip, get_ip())

        ext = extension(f.original)
        mimetype = get_mimetype(f.original)

        fragments = ['video', 'mobilevideo', 'image', 'audio']
        fragment_check = [ 
            (mimetype == 'image/gif' and not g.mobile) or mimetype.startswith('video'),
            mimetype.startswith('video') and g.mobile,
            (mimetype.startswith('image') and mimetype != 'image/gif') or (mimetype == 'image/gif' and g.mobile),
            mimetype.startswith('audio'),
        ] 

        for i, truth in enumerate(fragment_check):
            if truth:
                fragment = fragments[i] 

        return {
            'filename': f.hash,
            'original': f.original,
            'video': ext in VIDEO_EXTENSIONS,
            'loop': ext in LOOP_EXTENSIONS,
            'autoplay': ext in AUTOPLAY_EXTENSIONS,
            'compression': compression,
            'mimetype': mimetype,
            'can_delete': can_delete if can_delete is not None else 'check',
            'fragment': 'fragments/' + fragment + '.html'
        }

    def get(self, id):
        if ".." in id or id.startswith("/"):
            abort(403)

        if "." in id: 
            if os.path.exists(os.path.join(_cfg("storage_folder"), id)): # These requests are handled by nginx if it's set up
                path = os.path.join(_cfg("storage_folder"), id)
                return send_file(path, as_attachment=True)
    
        return render_template("view.html", **self._template_params(id))
    
    def report(self, id):
        f = File.from_hash(id)
        f.add_report()
        return "ok"

    @route("/<h>/delete")
    def delete(self, h):
        f = File.from_hash(h)
        if not f.original:
            abort(404)

        if not check_password_hash(f.ip, get_ip()):
            abort(401)

        delete_file(f)
        return "ok"

    @route("/<id>/direct")
    def direct(self, id):
        template_params = self._template_params(id)
        return render_template("direct.html", **template_params)

    @route("/<h>/frame")
    def frame(self, h):
        template_params = self._template_params(h)
        template_params['embedded'] = True
        return render_template("direct.html", **template_params)
