from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import logout
from django.core.context_processors import csrf
from django.core.exceptions import PermissionDenied
from django.core.mail import EmailMessage
from django.core.urlresolvers import reverse
from django.core.urlresolvers import reverse_lazy
from django.db.models import Q
from django.http import HttpResponseRedirect, Http404, HttpResponseForbidden
from django.shortcuts import render_to_response
from django.views.generic import DetailView, UpdateView, DeleteView, CreateView
from zues import models
from zues import forms
from zues.utils import current_site_id
from janeus import Janeus
import base64
import hashlib
import json
import os
import re
import logging


logger = logging.getLogger(__name__)


def generate_lid(lidnummer):
    lidnummer = int(lidnummer)
    if not hasattr(settings, 'JANEUS_SERVER'):
        res = (getattr(settings, 'DUMMY_MEMBER_EMAIL', b''), 'Onbekend lid'.encode('utf-8'))
    else:
        res = Janeus().attributes(lidnummer)
    if res is None:
        return None
    email, naam = res
    return _generate_lid(lidnummer, email.decode('utf-8'), naam.decode('utf-8'))


def _generate_lid(lidnummer, email, naam):
    code = hashlib.sha256(os.urandom(64)).hexdigest()

    lid = models.Login.objects.filter(lidnummer=lidnummer)
    if len(lid):
        # lid bestaat al
        lid = lid[0]
        lid.secret = hashlib.sha256(code.encode('utf-8')).hexdigest()
    else:
        # lid bestaat nog njet
        lid = models.Login(naam=naam, lidnummer=lidnummer, secret=hashlib.sha256(code.encode('utf-8')).hexdigest())

    lid.save()
    return (lid, email, naam, code)


def check_login(request):
    if 'lid' not in request.session:
        return None
    if 'key' not in request.session:
        return None
    leden = models.Login.objects.filter(lidnummer=int(request.session['lid'])).filter(secret=request.session['key'])
    if len(leden) == 0:
        try:
            del request.session['lid']
            del request.session['key']
        except KeyError:
            pass
        return None
    return leden[0]


def view_lidnummer(request):
    if request.method == 'POST':
        if getattr(settings, 'RECAPTCHA_PUBLIC_KEY', '') == '':
            form = forms.HelpLidnummerForm(request.POST)
        else:
            form = forms.HelpLidnummerRecaptchaForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            if getattr(settings, 'EMAIL_HOST', '') == '':
                return HttpResponseRedirect('/lidnummerverzonden/')
            if not hasattr(settings, 'JANEUS_SERVER'):
                return HttpResponseRedirect('/lidnummerverzonden/')

            for lidnummer, naam in Janeus().lidnummers(email):
                naam = naam.decode('utf-8')
                subject = '[JD] Lidnummer'
                from_email = 'noreply@jongedemocraten.nl'

                inhoud = []
                inhoud.append('Beste %s,' % naam)
                inhoud.append('')
                inhoud.append('Je hebt via de site van de Jonge Democraten je lidnummer opgevraagd. Je lidnummer is ' + str(lidnummer) + '.')
                inhoud.append('')
                inhoud.append('Met vrijzinnige groet,')
                inhoud.append('De Jonge Democraten.')
                inhoud = '\n'.join(inhoud)

                msg = EmailMessage(subject, inhoud, from_email=from_email, to=[email])
                msg.send()

            return HttpResponseRedirect('/lidnummerverzonden/')
    else:
        if getattr(settings, 'RECAPTCHA_PUBLIC_KEY', '') == '':
            form = forms.HelpLidnummerForm()
        else:
            form = forms.HelpLidnummerRecaptchaForm()

    context = {'form': form, }
    context.update(csrf(request))

    return render_to_response("zues/lidnummer.html", context)


def lidnummer_verzonden(request):
    return render_to_response("zues/lidnummerverzonden.html")


def get_categorieen(q=(Q(status=models.Stuk.GEACCEPTEERD) | Q(status=models.Stuk.PUBLIEK))):
    categories = []
    for obj in models.Categorie.objects.order_by('index'):
        cat = {}
        cat['prefix'] = obj.prefix
        cat['titel'] = obj.titel
        items = []
        items += obj.actuelepolitiekemotie_set.order_by('boeknummer').filter(q)
        items += obj.politiekemotie_set.order_by('boeknummer').filter(q)
        items += obj.organimo_set.order_by('boeknummer').filter(q)
        items += obj.resolutie_set.order_by('boeknummer').filter(q)
        items += obj.hrwijziging_set.order_by('boeknummer').filter(q)
        items += obj.amendement_set.order_by('boeknummer').filter(q)
        cat['items'] = items
        categories.append(cat)

    # cat contains all official categories with their items
    # now add homeless stuff

    cat = [c for c in categories if c['prefix'] == "PM"]
    if len(cat) == 0:
        cat = {'prefix': 'PM', 'titel': 'Politieke Moties', 'items': []}
        categories.append(cat)
    else:
        cat = cat[0]
    cat['items'] += models.PolitiekeMotie.objects.filter(q).filter(categorie=None)

    cat = [c for c in categories if c['prefix'] == "APM"]
    if len(cat) == 0:
        cat = {'prefix': 'APM', 'titel': 'Actuele Politieke Moties', 'items': []}
        categories.append(cat)
    else:
        cat = cat[0]
    cat['items'] += models.ActuelePolitiekeMotie.objects.filter(q).filter(categorie=None)

    cat = [c for c in categories if c['prefix'] == "RES"]
    if len(cat) == 0:
        cat = {'prefix': 'RES', 'titel': 'Resoluties', 'items': []}
        categories.append(cat)
    else:
        cat = cat[0]
    cat['items'] += models.Resolutie.objects.filter(q).filter(categorie=None)

    cat = [c for c in categories if c['prefix'] == "ORG"]
    if len(cat) == 0:
        cat = {'prefix': 'ORG', 'titel': 'Organimo\'s', 'items': []}
        categories.append(cat)
    else:
        cat = cat[0]
    cat['items'] += models.Organimo.objects.filter(q).filter(categorie=None)

    cat = [c for c in categories if c['prefix'] == "HR"]
    if len(cat) == 0:
        cat = {'prefix': 'HR', 'titel': 'HR-Wijzigingen', 'items': []}
        categories.append(cat)
    else:
        cat = cat[0]
    cat['items'] += models.HRWijziging.objects.filter(q).filter(categorie=None)

    cat = [c for c in categories if c['prefix'] == "AM"]
    if len(cat) == 0:
        cat = {'prefix': 'AM', 'titel': 'Amendementen', 'items': []}
        categories.append(cat)
    else:
        cat = cat[0]
    cat['items'] += models.Amendement.objects.filter(q).filter(categorie=None)

    return [c for c in categories if len(c['items']) > 0]


def view_home(request):
    lid = check_login(request)
    if lid:
        context = {}
        context['lid'] = lid
        context['pm'] = models.PolitiekeMotie.objects.filter(eigenaar=lid).exclude(status=models.Stuk.VERWIJDERD)
        context['apm'] = models.ActuelePolitiekeMotie.objects.filter(eigenaar=lid).exclude(status=models.Stuk.VERWIJDERD)
        context['org'] = models.Organimo.objects.filter(eigenaar=lid).exclude(status=models.Stuk.VERWIJDERD)
        context['res'] = models.Resolutie.objects.filter(eigenaar=lid).exclude(status=models.Stuk.VERWIJDERD)
        context['am'] = models.Amendement.objects.filter(eigenaar=lid).exclude(status=models.Stuk.VERWIJDERD)
        context['hr'] = models.HRWijziging.objects.filter(eigenaar=lid).exclude(status=models.Stuk.VERWIJDERD)
        context['count'] = len(context['pm']) + len(context['apm']) + len(context['org']) + len(context['res']) + len(context['am']) + len(context['hr'])
        context['settings'] = models.get_settings()
        context['staff'] = request.user.is_active and request.user.is_staff
        context['publiek'] = get_categorieen(Q(status=models.Stuk.PUBLIEK))
        context['allpm'] = models.PolitiekeMotie.objects.filter(status=models.Stuk.PUBLIEK)
        context['allapm'] = models.ActuelePolitiekeMotie.objects.filter(status=models.Stuk.PUBLIEK)
        context['allorg'] = models.Organimo.objects.filter(status=models.Stuk.PUBLIEK)
        context['allres'] = models.Resolutie.objects.filter(status=models.Stuk.PUBLIEK)
        context['allam'] = models.Amendement.objects.filter(status=models.Stuk.PUBLIEK)
        context['allhr'] = models.HRWijziging.objects.filter(status=models.Stuk.PUBLIEK)
        context['allcount'] = len(context['allpm']) + len(context['allapm']) + len(context['allorg']) + len(context['allres']) + len(context['allam']) + len(context['allhr'])
        return render_to_response("zues/yolo.html", context)

    if request.method == 'POST':
        if getattr(settings, 'RECAPTCHA_PUBLIC_KEY', '') == '':
            form = forms.LidnummerForm(request.POST)
        else:
            form = forms.LidnummerRecaptchaForm(request.POST)
        if form.is_valid():
            lidnummer = form.cleaned_data['lidnummer']

            # opzoeken email
            result = generate_lid(int(lidnummer))
            if result is not None:
                lid, to, naam, key = result

                secret_url = reverse('zues:login', kwargs={'key': key, 'lid': lid.lidnummer})
                secret_url = request.build_absolute_uri(secret_url)
                if not settings.DEBUG:
                    secret_url = re.sub(r'^http://', r'https://', secret_url)

                if getattr(settings, 'EMAIL_HOST', '') == '':
                    return HttpResponseRedirect(secret_url)

                subject = '[JD] Toegang voorstelsysteem {}'.format(request.get_host().lower())
                from_email = 'noreply@jongedemocraten.nl'

                inhoud = []
                inhoud.append('Beste %s,' % naam)
                inhoud.append('')
                inhoud.append('Je hebt toegang gevraagd tot het voorstelsysteem van de Jonge Democraten. ')
                inhoud.append('Dit systeem kun je gebruiken met de volgende persoonlijke geheime URL:')
                inhoud.append(secret_url)
                inhoud.append('')
                inhoud.append('Deze URL kun je ook gebruiken om jouw ingediende voorstellen in te zien, te wijzigen en terug te trekken. Deel deze URL dus niet met anderen!')
                inhoud.append('')
                inhoud.append('Mocht je een nieuwe URL aanvragen via de website, dan wordt de bovenstaande URL automatisch ongeldig.')
                inhoud.append('')
                inhoud.append('Met vrijzinnige groet,')
                inhoud.append('De Jonge Democraten.')
                inhoud = '\n'.join(inhoud)

                #msg = EmailMessage(subject, inhoud, from_email=from_email, to=[to])
                #msg.send()
                context = { 'emailtext': inhoud }
                return render_to_response("zues/logindebug.html", context)
            else:
                return HttpResponseRedirect('/loginverzonden/')
    else:
        if getattr(settings, 'RECAPTCHA_PUBLIC_KEY', '') == '':
            form = forms.LidnummerForm()
        else:
            form = forms.LidnummerRecaptchaForm()

    context = {'form': form, }
    context.update(csrf(request))

    return render_to_response("zues/home.html", context)


def view_publiek(request):
    lid = check_login(request)
    if lid is None:
        return HttpResponseRedirect('/')
    context = {'categories': get_categorieen(Q(status=models.Stuk.PUBLIEK))}
    return render_to_response("zues/publiek.html", context)


@staff_member_required
def view_export(request):
    context = {'categories': get_categorieen()}
    return render_to_response("zues/export.html", context)


@staff_member_required
def view_export_snc(request):
    context = {'categories': get_categorieen()}
    return render_to_response("zues/exportsnc.html", context)


@staff_member_required
def view_reorder(request):
    if request.method == 'POST':
        try:
            # assuming UTF-8 here...
            data = json.loads(request.body.decode('utf-8'))
        except TypeError as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception(e)
            raise e
        models.Categorie.objects.all().delete()
        for cat in data:
            if len(cat['items']) == 0:
                continue
            c = models.Categorie(prefix=cat['prefix'], titel=cat['titel'], index=int(cat['idx']))
            c.save()
            i = 1
            for k in cat['items']:
                if k.startswith("PM-"):
                    o = models.PolitiekeMotie.objects.get(pk=int(k[3:]))
                elif k.startswith("APM-"):
                    o = models.ActuelePolitiekeMotie.objects.get(pk=int(k[4:]))
                elif k.startswith("ORG-"):
                    o = models.Organimo.objects.get(pk=int(k[4:]))
                elif k.startswith("RES-"):
                    o = models.Resolutie.objects.get(pk=int(k[4:]))
                elif k.startswith("AM-"):
                    o = models.Amendement.objects.get(pk=int(k[3:]))
                elif k.startswith("HR-"):
                    o = models.HRWijziging.objects.get(pk=int(k[3:]))
                o.categorie = c
                o.boeknummer = i
                o.save()
                i = i + 1

    context = {'categories': get_categorieen()}
    return render_to_response("zues/reorder.html", context)


def login_verzonden(request):
    return render_to_response("zues/loginverzonden.html")


def login(request, lid, key):
    # controleer login
    hetlid = models.Login.objects.filter(lidnummer=lid).filter(secret=hashlib.sha256(key.encode('utf-8')).hexdigest())
    if len(hetlid):
        request.session['lid'] = lid
        request.session['key'] = hetlid[0].secret
        return HttpResponseRedirect('/')
    return render_to_response("zues/loginfout.html")


def loguit(request):
    try:
        del request.session['lid']
        del request.session['key']
    except KeyError:
        pass
    # ook uitloggen bij admin
    logout(request)
    return HttpResponseRedirect('/')


class SettingsMixin(object):
    def get_context_data(self, **kwargs):
        context = super(SettingsMixin, self).get_context_data(**kwargs)
        context['settings'] = models.get_settings()
        return context

    def dispatch(self, request, *args, **kwargs):
        if models.get_settings().public:
            return super(SettingsMixin, self).dispatch(request, *args, **kwargs)
        else:
            return HttpResponseForbidden()


class LidMixin(object):
    def get_context_data(self, **kwargs):
        context = super(LidMixin, self).get_context_data(**kwargs)
        if self.lid is not None:
            context['lid'] = self.lid
        return context

    def dispatch(self, request, *args, **kwargs):
        self.lid = check_login(request)
        return super(LidMixin, self).dispatch(request, *args, **kwargs)


class LoginMixin(object):
    def get_context_data(self, **kwargs):
        context = super(LoginMixin, self).get_context_data(**kwargs)
        if self.lid is not None:
            context['lid'] = self.lid
        return context

    def dispatch(self, request, *args, **kwargs):
        self.lid = check_login(request)
        if self.lid is None:
            return HttpResponseForbidden()
        return super(LoginMixin, self).dispatch(request, *args, **kwargs)


class EigenaarMixin(object):
    def get_object(self, **kwargs):
        obj = super(EigenaarMixin, self).get_object(**kwargs)
        if obj.eigenaar != self.lid:
            raise PermissionDenied()
        return obj

    def dispatch(self, request, *args, **kwargs):
        try:
            return super(EigenaarMixin, self).dispatch(request, *args, **kwargs)
        except PermissionDenied:
            return HttpResponseForbidden()


class MagWijzigenMixin(object):
    def get_object(self, **kwargs):
        obj = super(MagWijzigenMixin, self).get_object(**kwargs)
        if not obj.mag_wijzigen():
            raise PermissionDenied()
        return obj


class MagVerwijderenMixin(object):
    def get_object(self, **kwargs):
        obj = super(MagVerwijderenMixin, self).get_object(**kwargs)
        if not obj.mag_verwijderen():
            raise PermissionDenied()
        return obj


class SecretKeyMixin(object):
    def get_object(self, **kwargs):
        pk = self.kwargs['pk']
        try:
            # obj = super(SecretKeyMixin, self).get_object(**kwargs)
            obj = self.get_queryset().filter(pk=pk).get()
        except self.model.DoesNotExist:
            site_id = current_site_id()
            # if not found, let's also log all possible pk's...
            candidates = str(list(self.get_queryset().all().values_list('id', flat=True)))
            logger.warning("Http404 raised in SecretKeyMixin: NotFound for pk {} and site {}; candidates are {}".format(pk, site_id, candidates))
            raise Http404

        if self.kwargs['key'] != obj.secret:
            logger.warning("Http404 raised in SecretKeyMixin: Incorrect secret key for pk {}".format(pk))
            raise Http404
        return obj


class NoDeletedMixin(object):
    def get_queryset(self, **kwargs):
        return super(NoDeletedMixin, self).get_queryset(**kwargs).exclude(status=models.Stuk.VERWIJDERD)


class PMView(LidMixin, SettingsMixin, SecretKeyMixin, NoDeletedMixin, DetailView):
    template_name = 'zues/pm.html'
    context_object_name = "voorstel"
    model = models.PolitiekeMotie

    def get_context_data(self, **kwargs):
        context = super(PMView, self).get_context_data(**kwargs)
        context['mag'] = models.get_settings().mag_pm() and self.lid == context['voorstel'].eigenaar
        return context


class NieuwePM(LoginMixin, SettingsMixin, CreateView):
    model = models.PolitiekeMotie
    form_class = forms.PMForm
    template_name = 'zues/pmnew.html'

    def dispatch(self, request, *args, **kwargs):
        if not models.get_settings().mag_pm():
            return HttpResponseForbidden()
        else:
            return super(NieuwePM, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if 'preview' not in self.request.POST:
            self.object = form.save(commit=False)
            return self.render_to_response(self.get_context_data(form=form, obj=self.object))
        else:
            self.object = form.save(commit=False)
            self.object.secret = base64.urlsafe_b64encode(os.urandom(30))
            self.object.eigenaar = models.Login.objects.filter(lidnummer=self.request.session['lid'])[0]
            self.object.save()
            return HttpResponseRedirect(self.object.get_absolute_url())


class WijzigPM(LoginMixin, EigenaarMixin, MagWijzigenMixin, SettingsMixin, UpdateView):
    model = models.PolitiekeMotie
    form_class = forms.PMForm
    template_name = 'zues/pmnew.html'

    def get_context_data(self, **kwargs):
        context = super(WijzigPM, self).get_context_data(**kwargs)
        context['edit'] = 1
        return context


class VerwijderPM(LoginMixin, EigenaarMixin, MagVerwijderenMixin, SettingsMixin, DeleteView):
    model = models.PolitiekeMotie
    template_name = 'zues/pmdel.html'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.status = models.Stuk.VERWIJDERD
        self.object.save()
        return HttpResponseRedirect(reverse_lazy("zues:home"))


class APMView(LidMixin, SettingsMixin, SecretKeyMixin, NoDeletedMixin, DetailView):
    template_name = 'zues/apm.html'
    context_object_name = "voorstel"
    model = models.ActuelePolitiekeMotie

    def get_context_data(self, **kwargs):
        context = super(APMView, self).get_context_data(**kwargs)
        context['mag'] = models.get_settings().mag_apm() and self.lid == context['voorstel'].eigenaar
        return context


class NieuweAPM(LoginMixin, SettingsMixin, CreateView):
    model = models.ActuelePolitiekeMotie
    form_class = forms.APMForm
    template_name = 'zues/apmnew.html'

    def dispatch(self, request, *args, **kwargs):
        if not models.get_settings().mag_apm():
            return HttpResponseForbidden()
        else:
            return super(NieuweAPM, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if 'preview' not in self.request.POST:
            self.object = form.save(commit=False)
            return self.render_to_response(self.get_context_data(form=form, obj=self.object))
        else:
            self.object = form.save(commit=False)
            self.object.secret = base64.urlsafe_b64encode(os.urandom(30))
            self.object.eigenaar = models.Login.objects.filter(lidnummer=self.request.session['lid'])[0]
            self.object.save()
            return HttpResponseRedirect(self.object.get_absolute_url())


class WijzigAPM(LoginMixin, EigenaarMixin, MagWijzigenMixin, SettingsMixin, UpdateView):
    model = models.ActuelePolitiekeMotie
    form_class = forms.APMForm
    template_name = 'zues/apmnew.html'

    def get_context_data(self, **kwargs):
        context = super(WijzigAPM, self).get_context_data(**kwargs)
        context['edit'] = 1
        return context


class VerwijderAPM(LoginMixin, EigenaarMixin, MagVerwijderenMixin, SettingsMixin, DeleteView):
    model = models.ActuelePolitiekeMotie
    template_name = 'zues/apmdel.html'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.status = models.Stuk.VERWIJDERD
        self.object.save()
        return HttpResponseRedirect(reverse_lazy("zues:home"))


class ORGView(LidMixin, SettingsMixin, SecretKeyMixin, NoDeletedMixin, DetailView):
    template_name = 'zues/org.html'
    context_object_name = "voorstel"
    model = models.Organimo

    def get_context_data(self, **kwargs):
        context = super(ORGView, self).get_context_data(**kwargs)
        context['mag'] = models.get_settings().mag_org() and self.lid == context['voorstel'].eigenaar
        return context


class NieuweORG(LoginMixin, SettingsMixin, CreateView):
    model = models.Organimo
    form_class = forms.ORGForm
    template_name = 'zues/orgnew.html'

    def dispatch(self, request, *args, **kwargs):
        if not models.get_settings().mag_org():
            return HttpResponseForbidden()
        else:
            return super(NieuweORG, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if 'preview' not in self.request.POST:
            self.object = form.save(commit=False)
            return self.render_to_response(self.get_context_data(form=form, obj=self.object))
        else:
            self.object = form.save(commit=False)
            self.object.secret = base64.urlsafe_b64encode(os.urandom(30))
            self.object.eigenaar = models.Login.objects.filter(lidnummer=self.request.session['lid'])[0]
            self.object.save()
            return HttpResponseRedirect(self.object.get_absolute_url())


class WijzigORG(LoginMixin, EigenaarMixin, MagWijzigenMixin, SettingsMixin, UpdateView):
    model = models.Organimo
    form_class = forms.ORGForm
    template_name = 'zues/orgnew.html'

    def get_context_data(self, **kwargs):
        context = super(WijzigORG, self).get_context_data(**kwargs)
        context['edit'] = 1
        return context


class VerwijderORG(LoginMixin, EigenaarMixin, MagVerwijderenMixin, SettingsMixin, DeleteView):
    model = models.Organimo
    template_name = 'zues/orgdel.html'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.status = models.Stuk.VERWIJDERD
        self.object.save()
        return HttpResponseRedirect(reverse_lazy("zues:home"))


class RESView(LidMixin, SettingsMixin, SecretKeyMixin, NoDeletedMixin, DetailView):
    template_name = 'zues/res.html'
    context_object_name = "voorstel"
    model = models.Resolutie

    def get_context_data(self, **kwargs):
        context = super(RESView, self).get_context_data(**kwargs)
        context['mag'] = models.get_settings().mag_res() and self.lid == context['voorstel'].eigenaar
        return context


class NieuweRES(LoginMixin, SettingsMixin, CreateView):
    model = models.Resolutie
    form_class = forms.RESForm
    template_name = 'zues/resnew.html'

    def dispatch(self, request, *args, **kwargs):
        if not models.get_settings().mag_res():
            return HttpResponseForbidden()
        else:
            return super(NieuweRES, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if 'preview' not in self.request.POST:
            self.object = form.save(commit=False)
            return self.render_to_response(self.get_context_data(form=form, obj=self.object))
        else:
            self.object = form.save(commit=False)
            self.object.secret = base64.urlsafe_b64encode(os.urandom(30))
            self.object.eigenaar = models.Login.objects.filter(lidnummer=self.request.session['lid'])[0]
            self.object.save()
            return HttpResponseRedirect(self.object.get_absolute_url())


class WijzigRES(LoginMixin, EigenaarMixin, MagWijzigenMixin, SettingsMixin, UpdateView):
    model = models.Resolutie
    form_class = forms.RESForm
    template_name = 'zues/resnew.html'

    def get_context_data(self, **kwargs):
        context = super(WijzigRES, self).get_context_data(**kwargs)
        context['edit'] = 1
        return context


class VerwijderRES(LoginMixin, EigenaarMixin, MagVerwijderenMixin, SettingsMixin, DeleteView):
    model = models.Resolutie
    template_name = 'zues/resdel.html'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.status = models.Stuk.VERWIJDERD
        self.object.save()
        return HttpResponseRedirect(reverse_lazy("zues:home"))


class AMView(LidMixin, SettingsMixin, SecretKeyMixin, NoDeletedMixin, DetailView):
    template_name = 'zues/am.html'
    context_object_name = "voorstel"
    model = models.Amendement

    def get_context_data(self, **kwargs):
        context = super(AMView, self).get_context_data(**kwargs)
        context['mag'] = models.get_settings().mag_am() and self.lid == context['voorstel'].eigenaar
        return context


class NieuweAM(LoginMixin, SettingsMixin, CreateView):
    model = models.Amendement
    form_class = forms.AMForm
    template_name = 'zues/amnew.html'

    def dispatch(self, request, *args, **kwargs):
        if not models.get_settings().mag_am():
            return HttpResponseForbidden()
        else:
            return super(NieuweAM, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if 'preview' not in self.request.POST:
            self.object = form.save(commit=False)
            return self.render_to_response(self.get_context_data(form=form, obj=self.object))
        else:
            self.object = form.save(commit=False)
            self.object.secret = base64.urlsafe_b64encode(os.urandom(30))
            self.object.eigenaar = models.Login.objects.filter(lidnummer=self.request.session['lid'])[0]
            self.object.save()
            return HttpResponseRedirect(self.object.get_absolute_url())


class WijzigAM(LoginMixin, EigenaarMixin, MagWijzigenMixin, SettingsMixin, UpdateView):
    model = models.Amendement
    form_class = forms.AMForm
    template_name = 'zues/amnew.html'

    def get_context_data(self, **kwargs):
        context = super(WijzigAM, self).get_context_data(**kwargs)
        context['edit'] = 1
        return context


class VerwijderAM(LoginMixin, EigenaarMixin, MagVerwijderenMixin, SettingsMixin, DeleteView):
    model = models.Amendement
    template_name = 'zues/amdel.html'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.status = models.Stuk.VERWIJDERD
        self.object.save()
        return HttpResponseRedirect(reverse_lazy("zues:home"))


class HRView(LidMixin, SettingsMixin, SecretKeyMixin, NoDeletedMixin, DetailView):
    template_name = 'zues/hr.html'
    context_object_name = "voorstel"
    model = models.HRWijziging

    def get_context_data(self, **kwargs):
        context = super(HRView, self).get_context_data(**kwargs)
        context['mag'] = models.get_settings().mag_hr() and self.lid == context['voorstel'].eigenaar
        return context


class NieuweHR(LoginMixin, SettingsMixin, CreateView):
    model = models.HRWijziging
    form_class = forms.HRForm
    template_name = 'zues/hrnew.html'

    def dispatch(self, request, *args, **kwargs):
        if not models.get_settings().mag_hr():
            return HttpResponseForbidden()
        else:
            return super(NieuweHR, self).dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if 'preview' not in self.request.POST:
            self.object = form.save(commit=False)
            return self.render_to_response(self.get_context_data(form=form, obj=self.object))
        else:
            self.object = form.save(commit=False)
            self.object.secret = base64.urlsafe_b64encode(os.urandom(30))
            self.object.eigenaar = models.Login.objects.filter(lidnummer=self.request.session['lid'])[0]
            self.object.save()
            return HttpResponseRedirect(self.object.get_absolute_url())


class WijzigHR(LoginMixin, EigenaarMixin, MagWijzigenMixin, SettingsMixin, UpdateView):
    model = models.HRWijziging
    form_class = forms.HRForm
    template_name = 'zues/hrnew.html'

    def get_context_data(self, **kwargs):
        context = super(WijzigHR, self).get_context_data(**kwargs)
        context['edit'] = 1
        return context


class VerwijderHR(LoginMixin, EigenaarMixin, MagVerwijderenMixin, SettingsMixin, DeleteView):
    model = models.HRWijziging
    template_name = 'zues/hrdel.html'

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.status = models.Stuk.VERWIJDERD
        self.object.save()
        return HttpResponseRedirect(reverse_lazy("zues:home"))
