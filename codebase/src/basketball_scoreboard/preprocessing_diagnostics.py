"""Opt-in diagnostic hooks; capture tensor shapes, never media or credentials."""
from contextlib import contextmanager
from dataclasses import asdict,is_dataclass


def letterbox_image(image,size=640):
    import cv2
    height,width=image.shape[:2]
    ratio=min(size/width,size/height)
    nw,nh=max(1,round(width*ratio)),max(1,round(height*ratio))
    left,top=(size-nw)//2,(size-nh)//2
    resized=cv2.resize(image,(nw,nh),interpolation=cv2.INTER_LINEAR)
    boxed=cv2.copyMakeBorder(resized,top,size-nh-top,left,size-nw-left,cv2.BORDER_CONSTANT,value=(0,0,0))
    return boxed,dict(original_wh=[width,height],resized_wh=[nw,nh],pad_left=left,pad_top=top,
                      scale_x=nw/width,scale_y=nh/height,padding_color_bgr=[0,0,0])


def unletterbox_xyxy(box,transform):
    width,height=transform['original_wh']
    x1,y1,x2,y2=box
    result=[max(0.,min(width,(x1-transform['pad_left'])/transform['scale_x'])),
            max(0.,min(height,(y1-transform['pad_top'])/transform['scale_y'])),
            max(0.,min(width,(x2-transform['pad_left'])/transform['scale_x'])),
            max(0.,min(height,(y2-transform['pad_top'])/transform['scale_y']))]
    return result if result[2]>result[0] and result[3]>result[1] else None


def serializable_metadata(value):
    if hasattr(value,'_asdict'):return {k:serializable_metadata(v) for k,v in value._asdict().items()}
    if is_dataclass(value):return serializable_metadata(asdict(value))
    if hasattr(value,'model_dump'):return serializable_metadata(value.model_dump(mode='json'))
    if isinstance(value,dict):return {str(k):serializable_metadata(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [serializable_metadata(v) for v in value]
    if value is None or isinstance(value,(int,float,str,bool)):return value
    return str(value)


class _ObservedCpuSession:
    def __init__(self,session,records):self._original=session;self._records=records
    def __getattr__(self,name):return getattr(self._original,name)
    def run(self,*args,**kwargs):
        feeds=kwargs.get('input_feed',kwargs.get('inputs',args[1] if len(args)>1 else {}))
        self._records.append({str(name):list(array.shape) for name,array in feeds.items()})
        return self._original.run(*args,**kwargs)


@contextmanager
def observe_cpu_session(model):
    """Single-threaded diagnostics only; restore the verified SDK session on error."""
    original=model._session
    if original.get_providers()!=['CPUExecutionProvider']:
        raise ValueError('Only the approved CPU session may be observed')
    records=[]
    model._session=_ObservedCpuSession(original,records)
    try:yield records
    finally:model._session=original
