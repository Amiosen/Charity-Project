from rest_framework import status, generics
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsCharityOwner, IsBenefactor
from charities.models import Task
from charities.serializers import (
    TaskSerializer, CharitySerializer, BenefactorSerializer
)


class BenefactorRegistration(APIView):
    def post(self, request):
        benefactor_serializer = BenefactorSerializer(data=request.data)
        if benefactor_serializer.is_valid():
            benefactor_serializer.save(user=request.user)
            return Response(status=200)


class CharityRegistration(APIView):
    def post(self, request):
        charity_serializer = CharitySerializer(data=request.data)
        if charity_serializer.is_valid():
            charity_serializer.save(user=request.user)
            return Response(status=200)


class Tasks(generics.ListCreateAPIView):
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.all_related_tasks_to_user(self.request.user)

    def post(self, request, *args, **kwargs):
        data = {
            **request.data,
            "charity_id": request.user.charity.id
        }
        serializer = self.serializer_class(data = data)
        serializer.is_valid(raise_exception = True)
        serializer.save()
        return Response(serializer.data, status = status.HTTP_201_CREATED)

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            self.permission_classes = [IsAuthenticated, ]
        else:
            self.permission_classes = [IsCharityOwner, ]

        return [permission() for permission in self.permission_classes]

    def filter_queryset(self, queryset):
        filter_lookups = {}
        for name, value in Task.filtering_lookups:
            param = self.request.GET.get(value)
            if param:
                filter_lookups[name] = param
        exclude_lookups = {}
        for name, value in Task.excluding_lookups:
            param = self.request.GET.get(value)
            if param:
                exclude_lookups[name] = param

        return queryset.filter(**filter_lookups).exclude(**exclude_lookups)


class TaskRequest(APIView):
    def get(self, request, task_id):
        if request.user.is_benefactor:
            try:
                task = Task.objects.get(id = task_id)
                if not task.state == 'P':
                    return Response(data={'detail': 'This task is not pending.'}, status=404)
                task.assign_to_benefactor(request.user.benefactor)
                return Response(data={'detail': 'Request sent.'}, status=200) 
            except Task.DoesNotExist:
                return Response(status=404)
            
        else:
            return Response(status=403)

class TaskResponse(APIView):
    def post(self, request, task_id):
        task = Task.objects.get(id = task_id)
        if request.user.is_charity:
            if request.data['response'] != 'R' and request.data['response'] != 'A':
                return Response(
                    status=400,
                    data={'detail': 'Required field ("A" for accepted / "R" for rejected)'}
                    )
            if request.data['response'] == 'A' and task.state == 'W':
                task.response_to_benefactor_request(request.data['response'])
                return Response(
                    status=200,
                    data={'detail': 'Response sent.'}
                    )

            if request.data['response'] == 'R' and task.state == 'W':
                task.response_to_benefactor_request(request.data['response'])
                return Response(
                    status=200,
                    data={'detail': 'Response sent.'}
                    )
            
            return Response(
                    status=404,
                    data={'detail': 'This task is not waiting.'}
                    )

        else:
            return Response(status=403)


class DoneTask(APIView):
    def post(self, request, task_id):
        try:
            task = Task.objects.get(id = task_id)
            if request.user.is_charity:
                if task.state != 'A':
                    return Response(
                        status=404,
                        data={'detail': 'Task is not assigned yet.'}
                        )
                else:
                    task.done()
                    return Response(
                        status=200,
                        data={'detail': 'Task has been done successfully.'}
                        )
                    
            else:
                return Response(status=403)
                
            
        except Task.DoesNotExist:
            return Response(status=404)
        