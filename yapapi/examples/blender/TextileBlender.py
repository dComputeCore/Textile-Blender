from yapapi.runner import Engine, Task, vm
from yapapi.runner.ctx import WorkContext
from datetime import timedelta
import asyncio
import requests

async def main():
	package = await vm.repo(
    	image_hash="9a3b5d67b0b27746283cb5f287c13eab1beaa12d92a9f536b747c7ae",
    	min_mem_gib=0.5,
    	min_storage_gib=2.0,
	)

	url = 'https://hub.textile.io/ipfs/bafybeihpjl5e3vthvu6y33um4kuw6labeshl5utky556pg2tah4ngflvve'
	r = requests.get(url)

	with open('./cubes.blend', 'wb') as f:
		f.write(r.content)

	async def worker(ctx: WorkContext, tasks):
		ctx.send_file("./cubes.blend", "/golem/resource/scene.blend")
		async for task in tasks:
			frame = task.data
			ctx.begin()
			crops = [{"outfilebasename": "out", "borders_x": [0.0, 1.0], "borders_y": [0.0, 1.0]}]
			ctx.send_json(
				"/golem/work/params.json",
				{
					"scene_file": "/golem/resource/scene.blend",
					"resolution": (400, 300),
					"use_compositing": False,
					"crops": crops,
					"samples": 100,
					"frames": [frame],
					"output_format": "PNG",
					"RESOURCES_DIR": "/golem/resources",
					"WORK_DIR": "/golem/work",
					"OUTPUT_DIR": "/golem/output",
				},
			)
			ctx.run("/golem/entrypoints/run-blender.sh")
			ctx.download_file(f"/golem/output/out{frame:04d}.png", f"output_{frame}.png")
			yield ctx.commit()
            # TODO: Check if job results are valid
            # and reject by: task.reject_task(msg = 'invalid file')
			task.accept_task()

		ctx.log("no more frames to render")

    # iterator over the frame indices that we want to render
	frames: range = range(0, 60, 10)
    # TODO make this dynamic, e.g. depending on the size of files to transfer
    # worst-case time overhead for initialization, e.g. negotiation, file transfer etc.
	init_overhead: timedelta = timedelta(minutes=3)

	async with Engine(
		package=package,
		max_workers=3,
		budget=10.0,
		timeout=init_overhead + timedelta(minutes=len(frames) * 2),
		subnet_tag="testnet",
	) as engine:

		async for progress in engine.map(worker, [Task(data=frame) for frame in frames]):
			print("progress=", progress)


if __name__ == "__main__":
	loop = asyncio.get_event_loop()
	task = loop.create_task(main())
	try:
		asyncio.get_event_loop().run_until_complete(task)
	except (Exception, KeyboardInterrupt) as e:
		print(e)
		task.cancel()
		asyncio.get_event_loop().run_until_complete(asyncio.sleep(0.3))