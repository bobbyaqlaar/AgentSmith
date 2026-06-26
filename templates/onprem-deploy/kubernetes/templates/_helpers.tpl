{{- define "onprem.fullname" -}}
{{- .Release.Name -}}
{{- end -}}

{{- define "onprem.gatewayClassName" -}}
{{- if .Values.gatewayClassName -}}
{{ .Values.gatewayClassName }}
{{- else if eq .Values.proxyEngine "envoy-gateway" -}}
eg
{{- else -}}
traefik
{{- end -}}
{{- end -}}

{{/*
Shared env block for app containers — plain values.env merged with an
optional envSecretName's keys via envFrom. Used by deployment-*.yaml.
*/}}
{{- define "onprem.envFrom" -}}
{{- if .Values.envSecretName }}
envFrom:
  - secretRef:
      name: {{ .Values.envSecretName }}
{{- end }}
{{- end -}}

{{- define "onprem.env" -}}
{{- range $k, $v := .Values.env }}
- name: {{ $k }}
  value: {{ $v | quote }}
{{- end }}
{{- end -}}
