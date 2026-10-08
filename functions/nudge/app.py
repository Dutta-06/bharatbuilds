"""nudge: last step of the forecast pipeline. Emails (SNS) once when a much better window has
opened for a job that is still waiting to start. Advisory only; nothing is changed.
"""

from backend import replan


def handler(event, context):
    return replan.nudge_all()
