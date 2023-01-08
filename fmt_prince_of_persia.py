from inc_noesis import *

import noesis
import rapi
import struct
import binascii
import math

def registerNoesisTypes():
	handle = noesis.register("PrinceOfPersiaTT", ".bin")
	noesis.setHandlerTypeCheck(handle, noepyCheckType)
	noesis.setHandlerLoadModel(handle, noepyLoadModel)
	noesis.logPopup()
	return 1

def noepyCheckType(data):
	return 1

IDToIndex 						=	dict()
parentLocalQuat					=	[]
def getSkelleton():	
	data 						=	open("PrinceFinal_Shape_wow.bin", "rb").read()
	fs 							=	NoeBitStream(data)
	addr 						=	0x00013ADF
	fs.seek(addr, NOESEEK_ABS)
	bones 						=	[]
	bone_count 					=	34
	
	
	for i in range(0, bone_count):
		blockSize				=	fs.readUInt()
		blockTag				=	hex(fs.readUInt())
		blockID					=	fs.readUShort()
		unknown 				=	fs.readBytes(18)
		nameLength 				=	fs.readUInt()		
		name 					=	noeStrFromBytes(fs.readBytes(nameLength), "ASCII")
		unknown 				=	fs.readBytes(10)
		
		mat44 					=	NoeMat44.fromBytes(fs.readBytes(64))
		boneMat 				=	mat44.toMat43()
		
		unknown 				=	fs.readBytes(52)
		parentID				=	fs.readUShort()	
		IDToIndex[str(blockID)]	=	i
		bones.append( 				NoeBone(blockID, name, boneMat, None, parentID))

		fs.seek(addr + blockSize + 12)
		addr = addr + (blockSize + 12)	
	
#	bones.append( 					NoeBone(99, "B_Pr_Bip Root.gao", NoeMat43()))
#	IDToIndex["99"]				=	99
	
	#	LOCAL TO GLOBAL MATRIX
	for i in range(0,bone_count):
		if	bones[i].index 		!= 	8932:
			parentLocalQuat.append(	bones[IDToIndex[str(bones[i].parentIndex)]].getMatrix().toQuat()	)
			bones[i].setMatrix( bones[i].getMatrix() * bones[IDToIndex[str(bones[i].parentIndex)]].getMatrix() )
	
	#	CONVERT INDEX FORMAT
	for i in range(0,bone_count):
		if	bones[i].index != 8932:
			bones[i].index			=	IDToIndex[str(bones[i].index)]
			bones[i].parentIndex	=	IDToIndex[str(bones[i].parentIndex)]
		if	bones[i].index == 8932:
			bones[i].index			=	0
			bones[i].parentIndex	=	99
#			bones[i].parentIndex	=	-1
	return bones
	
flagListAnim 	= [hex(0xfa03),hex(0xfa00),hex(0xfe03),hex(0xea00),hex(0xf800),hex(0xfa07)]
flagListDiv		= [hex(0x4017),hex(0x0000),hex(0x4014)]
def validateBlock(trackSize, trackFrame, flag, boneID):
	if trackSize 	< 0:		return 0
	if trackFrame 	< 0:		return 0
	if boneID 		!= 0xFFFF:	return 0
	if flag in flagListAnim:	return 1
	return 0
	
def findAnimationBlocks(bs):
	#	=================================
	#	|			BLOCKS				|
	#	=================================
	#	BLOCK_HEAD
	#	[
	#		4	blockSize	00000000
	#		4	blockTag	99C0FFEE	(ALWAYS)
	#		4	blockID		00000000
	#	]
	#	TRAVERSE TROUGH ALL AVAIABLE BLOCKS
	blockArray			=	[]
	for i in range(0,1000):
		blockAddr		=	bs.tell()
		blockSize		=	bs.readUInt()
		blockTag		=	hex(bs.readUInt())
		blockID			=	hex(bs.readUInt())
		addr			=	bs.tell()
		
		#	REACHED END OF FILE
		if blockID ==	hex(0xff7c0de):
			return blockArray
	
		trackSize		=	bs.readUShort()
		trackFrame		=	bs.readUShort()
		flag			=	hex(bs.readUShort())
		boneID			=	bs.readUShort()
	
		if validateBlock(trackSize, trackFrame, flag, boneID) == 0:
			#	JUMP TO THE NEXT BLOCK
			bs.seek(addr + blockSize, NOESEEK_ABS)	
			continue
	
		blockArray.append(blockAddr)
		bs.seek(addr + blockSize, NOESEEK_ABS)
	return blockArray
	
def noepyLoadModel(data, mdlList): 
	#	=================================
	#	|			ANIMATION			|
	#	=================================	
	ctx 				=	rapi.rpgCreateContext()
	rapi.					rpgClearBufferBinds()
	keyDurations 		= 	[]
	bones				=	getSkelleton()
	kfbones 			=	[]
	bs 					=	NoeBitStream(data)
	fileSize 			=	bs.getSize()
	animBlocks 			=	findAnimationBlocks(bs)
	anim_bones_rot		=	dict()
	anim_bones_vec		=	dict()
	anim_tracks			=	dict()
	anims 				=	[]	
	anim_counter		=	0
		
	for animAddr in animBlocks:
		anim_counter	=	anim_counter + 1
		bs.seek(animAddr,	NOESEEK_ABS)
		kfbones 		=	[]
		blockSize		= 	bs.readUInt()
		blockTag		= 	hex(bs.readUInt())
		blockID			= 	hex(bs.readUInt())
		trackCount		= 	bs.readUShort()				#	trackCount
		trackFrame		= 	bs.readUShort()				#	trackFrameNum_A		
		for track in range(0, trackCount):
			frame 			=	1						#	init start frame
			flag_01			= 	hex(bs.readUShort())	#	flags
			boneID			= 	bs.readShort()			#	boneID
			trackSize		= 	bs.readUInt()			#	trackSize		
			trackFrameNum	=	bs.readUInt()			#	trackFrameNum_B
			frameLength		=	bs.readByte()			#	trackFrameLen	
			flag_02			=	bs.readByte()			#	trackFrameTypeFlags
			unknown			=	bs.readByte()			#	---			
			keyType			=	bs.readByte()			#	---
			unknown			=	bs.readBytes(2)			#	---
														#	0x90	uncrompressed quaternion	in BGE
														#	0x10	part3case0 quaternion		in BGE
														#	0x01	part3case1 vec3				in BGE
			if flag_01 in flagListDiv:	break			#	0x4017	skip programcode
			keyDurations.		append(trackFrameNum)
			anim_rot_frames		=	dict()
			anim_vec_frames		=	dict()
			
			for key in range(0,trackFrameNum):
				if hex(keyType) == hex(0x10):
					duration 	=	int(bs.readByte())	#	freq
					v1			=	bs.readFloat()		#	f1
					v2			=	bs.readFloat()		#	f2
					v3			=	bs.readFloat()		#	f3				
					anim_vec_frames[frame]	=	NoeVec3((v1, v2, v3))
					frame 					=	frame + (1 * duration)
					
				if hex(keyType) == hex(0x08):
					duration	=	int(bs.readByte())											
					compressed	=	bs.readUInt()
					v 			=	compressed & 0xC0000000
					#	range		=	1 / math.sqrt(2)
					#	norm		=	range / 512
					
					if duration == 64 or duration == 0:
						duration = 1
					#	continue
			
					if v == 0:
						v1		=	float(((compressed >> 20) & 0x3FF) * 0.0013810679 - 0.70710677);
						v2		=	float(((compressed >> 10) & 0x3FF) * 0.0013810679 - 0.70710677);
						v3		=	float(((compressed >> 00) & 0x3FF) * 0.0013810679 - 0.70710677);
						v0		=	float(math.sqrt(1.0 - pow(v1,2) - pow(v2,2) - pow(v3,2)))
					
					if v == 0x40000000:
						v0		=	float(((compressed >> 20) & 0x3FF) * 0.0013810679 - 0.70710677);
						v2		=	float(((compressed >> 10) & 0x3FF) * 0.0013810679 - 0.70710677);
						v3		=	float(((compressed >> 00) & 0x3FF) * 0.0013810679 - 0.70710677);
						v1		=	float(math.sqrt(1.0 - pow(v0,2) - pow(v2,2) - pow(v3,2)))

					if v == 0x80000000:
						v0		=	float(((compressed >> 20) & 0x3FF) * 0.0013810679 - 0.70710677);
						v1		=	float(((compressed >> 10) & 0x3FF) * 0.0013810679 - 0.70710677);
						v3		=	float(((compressed >> 00) & 0x3FF) * 0.0013810679 - 0.70710677);
						v2		=	float(math.sqrt(1.0 - pow(v0,2) - pow(v1,2) - pow(v3,2)))
						
					if v == 0xC0000000:
						v0		=	float(((compressed >> 20) & 0x3FF) * 0.0013810679 - 0.70710677);
						v1		=	float(((compressed >> 10) & 0x3FF) * 0.0013810679 - 0.70710677);
						v2		=	float(((compressed >> 00) & 0x3FF) * 0.0013810679 - 0.70710677);
						v3		=	float(math.sqrt(1.0 - pow(v0,2) - pow(v1,2) - pow(v2,2)))
														
					anim_rot_frames[frame]	=	NoeQuat((v0, v1, v2, v3)).transpose()
					frame 					=	frame + (1 * duration)			
			#END OF KEYS			
		#	if boneID == -1: boneID 	=	99
			if len(anim_rot_frames) != 0:	anim_bones_rot[boneID] = anim_rot_frames
			if len(anim_vec_frames) != 0:	anim_bones_vec[boneID] = anim_vec_frames
					
		#END OF TRACKS	
		for bone in anim_bones_rot:
			rotationKeys 					= 	[]
			translationKeys 				=	[]
			
			if bone in anim_bones_rot:
				for anim_frame in anim_bones_rot[bone]:
					frame						=	anim_frame
					quat 						=	anim_bones_rot[bone][anim_frame]				
					rotationKeys.					append(NoeKeyFramedValue(frame, quat	))	
			if bone in anim_bones_vec:
				for anim_frame in anim_bones_vec[bone]:
					frame						=	anim_frame
					vec							=	anim_bones_vec[bone][anim_frame]
					translationKeys.				append(NoeKeyFramedValue(frame, vec		))	

			skip							=	False
			for ele in kfbones:
				if ele.boneIndex == bone:
					if len(rotationKeys 	!= 0):	ele.setRotation(rotationKeys)
					if len(translationKeys 	!= 0):	ele.setTranslation(translationKeys)
					skip					=	True
					
			if not(skip):
				kfbone 						= 	NoeKeyFramedBone(bone)
				if len(rotationKeys) 	!= 0:	kfbone.setRotation(rotationKeys)	
				if len(translationKeys)	!= 0:	kfbone.setTranslation(translationKeys)	
				kfbones.						append(kfbone)		
		
		#if anim_counter == 42:
		anims.append(NoeKeyFramedAnim("anim_" + str(blockID), bones, kfbones, 1.0))				
		
	mdl = NoeModel()
	mdl.setBones(bones)
	mdl.setAnims(anims)
	mdlList.append(mdl)
	
	rapi.setPreviewOption("setAngOfs", "0 0 0")
	rapi.setPreviewOption("setAnimSpeed", "10")
	return 1