# tasks-api

Навчальний REST API на Flask, який я використовую як наскрізний проєкт для практики DevOps: контейнеризація, Kubernetes (k3s) та автоматизація через Ansible.

## Що в репозиторії

- `app/` — Flask API (дані зберігаються в пам'яті, без БД) і Dockerfile
- `k3s/` — маніфести Kubernetes: Deployment (1 репліка) і Service (NodePort 30000)
- `ansible/` — роль `k3s_install` (встановлення k3s) і два плейбуки: для віддаленого хоста та для localhost

## API

| Метод | Шлях | Опис |
|---|---|---|
| GET | `/` | веб-інтерфейс |
| GET | `/health` | перевірка стану |
| GET, POST | `/tasks` | список / створення задач |
| GET, PUT, DELETE | `/tasks/<id>` | читання / оновлення / видалення |

Приклади запитів — у `requests.http`.

## Запуск у Docker

```bash
docker build -t tasks-api:1.0 app/
docker run --rm -p 8080:8080 tasks-api:1.0
curl http://localhost:8080/health
```

## Запуск у Kubernetes (k3s)

```bash
kubectl apply -f k3s/
kubectl get pods,svc
curl http://<NODE_IP>:30000/health
```

## Ansible

Встановлення k3s на локальній машині:

```bash
ansible-playbook ansible/playbook-local.yml --ask-become-pass
```

Для віддаленого хоста скопіюй `ansible/inventory.example.yml` в `ansible/inventory.yml`, підстав свої значення (файл у `.gitignore`) і переконайся, що ім'я хоста збігається з `hosts` у `playbook.yml`.

## Статус і плани

Зараз це робочий мінімум. Ще не зроблено і заплановано:

- [ ] CI/CD пайплайн (збірка образу, push у registry, деплой)
- [ ] liveness/readiness probes і resource limits у маніфестах
- [ ] Terraform для інфраструктури
- [ ] моніторинг (Prometheus + Grafana)
- [ ] зберігання даних у БД замість пам'яті
